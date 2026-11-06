"""Shot boundary detection: hard cuts, fades through black/white, dissolves.

Works on tiny thumbnails of every frame (cheap) and combines a colour-histogram
distance with a pixel difference so lighting flicker and fast motion do not fire
spurious cuts. Thresholds are adaptive to the local activity level."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .media import VideoInfo, frame_times, iter_frames

THUMB_W = 96


@dataclass
class FrameTrack:
    fps: float
    hist_dist: np.ndarray       # bhattacharyya distance to previous frame (0..1)
    pix_diff: np.ndarray        # mean |diff| of gray thumbs, 0..1
    changed: np.ndarray         # fraction of thumb pixels that changed noticeably
    luma: np.ndarray            # mean luma 0..255
    thumbs: list[np.ndarray] = field(repr=False, default_factory=list)  # small gray thumbs, uint8 (for dissolve check)
    hists: list[np.ndarray] = field(repr=False, default_factory=list)
    times: np.ndarray | None = field(repr=False, default=None)  # per-frame pts (s) for variable frame rate; None = i / fps

    @property
    def n(self) -> int:
        return len(self.luma)


@dataclass
class Shot:
    index: int
    start_frame: int
    end_frame: int  # exclusive
    fps: float
    transition_in: str = "cut"
    boundary_score: float = 0.0
    beats: list[int] = field(default_factory=list)  # frame indices of MG/slide beat changes inside the shot
    flash_s: float = 0.0  # "flash" transitions: how long the white / grey flash takes to decay
    times: np.ndarray | None = field(repr=False, default=None)  # FrameTrack.times

    def t(self, frame: int) -> float:
        """Time of a frame index. Variable-frame-rate video uses the real pts; past the last frame,
        one median frame interval after it."""
        if self.times is None:
            return frame / self.fps
        if frame < len(self.times):
            return float(self.times[frame])
        step = float(np.median(np.diff(self.times))) if len(self.times) > 1 else 1 / self.fps
        return float(self.times[-1]) + step * (frame - len(self.times) + 1)

    @property
    def start(self) -> float:
        return self.t(self.start_frame)

    @property
    def end(self) -> float:
        return self.t(self.end_frame)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"index": self.index, "start": round(self.start, 3), "end": round(self.end, 3),
                "duration": round(self.duration, 3), "start_frame": self.start_frame, "end_frame": self.end_frame,
                "transition_in": self.transition_in, "boundary_score": round(self.boundary_score, 3),
                "beats": [round(self.t(b), 3) for b in self.beats]} | ({"flash_s": round(self.flash_s, 2)} if self.flash_s else {})


def _hist(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 4, 4], [0, 180, 0, 256, 0, 256])
    cv2.normalize(h, h, alpha=1.0, norm_type=cv2.NORM_L1)
    return h.flatten().astype(np.float32)


def build_track(path: str, info: VideoInfo) -> FrameTrack:
    hist_d, pix_d, chg, luma, thumbs, hists = [], [], [], [], [], []
    prev_h = prev_g = None
    for bgr in iter_frames(path, info, THUMB_W):
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h = _hist(bgr)
        if prev_h is None:
            hist_d.append(0.0)
            pix_d.append(0.0)
            chg.append(0.0)
        else:
            d = np.abs(g - prev_g)
            hist_d.append(float(cv2.compareHist(prev_h, h, cv2.HISTCMP_BHATTACHARYYA)))
            pix_d.append(float(d.mean() / 255.0))
            thr = max(6.0, 0.35 * float(min(g.std(), prev_g.std())))
            chg.append(float((d > thr).mean()))
        luma.append(float(g.mean()))
        thumbs.append(g.astype(np.uint8))  # lossless (gray of uint8 frames); 4x less memory on long videos
        hists.append(h)
        prev_h, prev_g = h, g
    fps = info.fps if info.fps > 0 else 30.0
    return FrameTrack(fps=fps, hist_dist=np.array(hist_d), pix_diff=np.array(pix_d), changed=np.array(chg), luma=np.array(luma),
                      thumbs=thumbs, hists=hists, times=frame_times(path, len(luma), fps))


def _local_median(x: np.ndarray, radius: int) -> np.ndarray:
    out = np.empty_like(x)
    n = len(x)
    for i in range(n):
        lo, hi = max(0, i - radius), min(n, i + radius + 1)
        window = np.concatenate([x[lo:i], x[i + 1:hi]]) if hi - lo > 1 else x[lo:hi]
        out[i] = np.median(window) if len(window) else 0.0
    return out


def detect_shots(track: FrameTrack, min_shot_s: float = 0.35, cut_threshold: float = 0.30,
                 dissolve: bool = True) -> list[Shot]:
    n = track.n
    if n == 0:
        return []
    fps = track.fps
    score = 0.6 * track.hist_dist + 0.4 * np.clip(track.pix_diff * 4.0, 0, 1)
    score[0] = 0.0
    radius = max(4, int(round(fps * 0.5)))
    base = _local_median(score, radius)
    boundaries: dict[int, tuple[str, float]] = {}

    # 1) hard cuts: a spike well above local activity that changes most of the frame
    #    (a title popping in over a static layout changes only a region -> not a cut)
    chg = track.changed
    chg_base = _local_median(chg, radius)
    for i in range(1, n):
        s = score[i]
        strong = s > cut_threshold and s > base[i] * 2.5 + 0.06 and chg[i] > 0.25
        relative = chg[i] > 0.45 and chg[i] > chg_base[i] * 3 + 0.2 and s > base[i] * 4 + 0.03
        # a one-frame swap between two still layouts (slides / MG cards on the same ground): less of the frame
        # changes, but the colour distribution jumps and the picture before it is digitally frozen (pixel-identical
        # frames; a filmed screen whose content changes keeps sensor noise, 0.002-0.03, and is not a cut)
        still_swap = (s > cut_threshold and track.hist_dist[i] > 0.25 and chg[i] > 0.18 and chg_base[i] < 0.01
                      and s > base[i] * 5 + 0.1 and i >= 3 and float(track.pix_diff[i - 3:i].max()) < 1e-3)
        if strong or relative or still_swap:
            boundaries[i] = ("cut", float(max(s, chg[i])))

    # 2) fades through black / white: luma dips to an extreme and comes back
    lo_l = min(10.0, float(np.percentile(track.luma, 50)) * 0.35)
    dark = (track.luma < lo_l) | (track.luma > 248)
    i = 0
    while i < n:
        if dark[i]:
            j = i
            while j < n and dark[j]:
                j += 1
            # a fade passes through an (almost) uniform frame; a white page with a title on it is a shot, not a fade
            flat = min(float(track.thumbs[k].std()) for k in range(i, j)) < 4.0
            if 0 < i and j < n and (j - i) <= fps * 2.5 and flat:
                # boundary at the last extreme frame (next shot starts after fade-in begins)
                mid = j
                if not any(abs(mid - b) < radius for b in boundaries):
                    boundaries[mid] = ("fade", 0.5)
            i = j
        else:
            i += 1

    # 3) dissolves / cross-fades: frame i is a linear blend of frames i-k and i+k.
    #    (camera or subject motion also changes the picture over 2k frames, but the middle
    #    frame of a move is not a blend of its endpoints, so the blend residual separates them)
    if dissolve and n > 2 * fps:
        for k in sorted({max(2, int(round(fps * 0.12))), max(3, int(round(fps * 0.2))), max(5, int(round(fps * 0.45)))}):
            cand = []
            for i in range(k, n - k):
                A, B, M = (track.thumbs[j].astype(np.float32) for j in (i - k, i + k, i))
                D = B - A
                thr = max(6.0, 0.35 * float(min(A.std(), B.std())))
                far = float((np.abs(D) > thr).mean())
                if far < 0.15 or float(score[i - k + 1:i + k + 1].max()) >= cut_threshold:
                    continue
                denom = float((D * D).sum())
                if denom <= 0:
                    continue
                alpha = float(((M - A) * D).sum() / denom)
                if not 0.2 <= alpha <= 0.8:
                    continue
                resid = float(np.abs(M - (A + alpha * D)).mean() / (np.abs(D).mean() + 1e-6))
                # a cross-fade is a burst of change; an animated gradient / colour morph is a blend of its
                # neighbours at every frame, at a steady rate, so require more change than in the windows around it
                if resid < 0.20 and not _steady_morph(track.thumbs, i, k) and not _motion_explains(A, B):
                    cand.append((i, resid, far))
            cand.sort(key=lambda t: t[1])
            for i, resid, far in cand:
                if all(abs(i - bnd) > 2 * k for bnd in boundaries):
                    boundaries[i] = ("dissolve", round(1 - resid, 3))

    beat_marks = [b for b, _ in _mg_beats(track, boundaries, fps)]

    # assemble shots, enforce minimum length (merge short ones into previous)
    min_len = max(1, int(round(min_shot_s * fps)))
    cuts = sorted(boundaries)
    shots: list[Shot] = []
    start, trans, bscore = 0, "start", 0.0
    for b in cuts + [n]:
        if b - start < min_len and b != n:
            continue
        if b == n and shots and b - start < min_len:
            shots[-1].end_frame = n
            break
        shots.append(Shot(index=len(shots) + 1, start_frame=start, end_frame=b, fps=fps, transition_in=trans, boundary_score=bscore,
                              times=track.times))
        if b < n:
            trans, bscore = boundaries[b]
        start = b
    for shot in shots:
        shot.beats = [b for b in beat_marks if shot.start_frame + min_len <= b <= shot.end_frame - min_len]
        if shot.transition_in == "cut":
            shot.flash_s = _flash(track.luma, shot.start_frame, shot.end_frame, fps)
            if shot.flash_s:
                shot.transition_in = "flash"
    return shots


def _flash(luma: np.ndarray, start: int, end: int, fps: float) -> float:
    """A cut that opens on a bright flash decaying into the new shot (a common motion-graphics transition):
    seconds until the brightness settles, or 0."""
    if start < 1 or end - start < 3:
        return 0.0
    before = float(np.median(luma[max(0, start - 3):start]))
    settle = float(np.median(luma[start + 1:end][-max(1, min(end - start - 1, int(fps))):]))  # level later in the shot
    jump = float(luma[start]) - max(before, settle)
    if jump < 40:
        return 0.0
    k = start
    while k + 1 < end and luma[k + 1] - settle > 0.2 * jump:
        k += 1
    if k == start or k - start > fps * 1.5:  # one bright frame is just a bright shot; a long ramp is a fade
        return 0.0
    return (k + 1 - start) / fps


def _mg_beats(track: FrameTrack, boundaries: dict[int, tuple[str, float]], fps: float) -> list[tuple[int, tuple[str, float]]]:
    """Find 'holds' (runs of frozen frames >= 0.4 s). Consecutive holds whose frames differ
    over a large area are different beats of a rendered (MG/slide) video."""
    n = track.n
    frozen = track.changed < 0.004
    min_run = max(3, int(round(0.4 * fps)))
    runs: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if frozen[i]:
            j = i
            while j < n and frozen[j]:
                j += 1
            if j - i >= min_run:
                runs.append((i, j))
            i = j
        else:
            i += 1
    out: list[tuple[int, tuple[str, float]]] = []
    for (a0, a1), (b0, b1) in zip(runs, runs[1:]):
        if any(a1 - 1 <= k <= b0 + 1 for k in boundaries):
            continue  # already separated by a detected cut/fade
        ta, tb = (track.thumbs[j].astype(np.float32) for j in ((a0 + a1) // 2, (b0 + b1) // 2))
        thr = max(6.0, 0.35 * float(min(ta.std(), tb.std())))
        frac = float((np.abs(ta - tb) > thr).mean())
        if frac > 0.12:
            # boundary at the start of the transition (end of hold A)
            out.append((a1, ("mg_transition", frac)))
    return out


def _steady_morph(thumbs: list[np.ndarray], i: int, k: int) -> bool:
    """True when the picture changes as fast just before and just after the window [i-k, i+k] as inside it."""
    n = len(thumbs)

    def rate(a: int, b: int) -> float | None:
        a, b = max(0, a), min(n - 1, b)
        if b - a < k:
            return None
        return float(np.abs(thumbs[b].astype(np.float32) - thumbs[a].astype(np.float32)).mean()) * (2 * k) / (b - a)

    mid = rate(i - k, i + k)
    around = [r for r in (rate(i - 3 * k, i - k), rate(i + k, i + 3 * k)) if r is not None]
    return bool(mid and around and mid < 1.3 * max(around))


def _motion_explains(a: np.ndarray, b: np.ndarray) -> bool:
    """True when b is (mostly) a warped copy of a (zoom/pan/subject motion), i.e. the change
    between them is movement rather than new content fading in."""
    a8 = np.clip(a, 0, 255).astype(np.uint8)
    b8 = np.clip(b, 0, 255).astype(np.uint8)
    flow = cv2.calcOpticalFlowFarneback(a8, b8, None, 0.5, 3, 9, 3, 5, 1.1, 0)
    h, w = a8.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    warped = cv2.remap(b8, gx + flow[..., 0], gy + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    m = 4  # ignore borders
    before = float(np.abs(b8.astype(np.float32) - a8.astype(np.float32))[m:-m, m:-m].mean())
    after = float(np.abs(warped.astype(np.float32) - a8.astype(np.float32))[m:-m, m:-m].mean())
    return after < 0.45 * before
