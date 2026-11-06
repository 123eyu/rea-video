"""Per-shot forensic features.

Spatial  : sensor-like noise, perfectly flat blocks, palette size, axis-aligned edges,
           saturation — separate rendered graphics from photographic images.
Temporal : duplicate frames (and their periodicity, e.g. 24→30 fps conversion typical of
           generator output), exactly-unchanged pixels, temporal noise in still areas.
Motion   : global similarity-transform fit (zoom/pan/rotate) with RANSAC, residual
           parallax and local motion — detects "still image + push/pan" (Ken Burns),
           tripod vs handheld, and how much of the frame actually moves."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from .media import VideoInfo, iter_frames
from .shots import Shot

ANALYSIS_W = 480
_IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)


@dataclass
class ShotSamples:
    frames: list[np.ndarray] = field(default_factory=list)        # sampled BGR frames (ANALYSIS_W)
    frame_times: list[float] = field(default_factory=list)
    pair_mad: list[float] = field(default_factory=list)           # mean |diff| for every consecutive pair
    pair_zero: list[float] = field(default_factory=list)          # fraction of exactly-unchanged pixels
    pair_tnoise: list[float] = field(default_factory=list)        # median |diff| over near-still pixels
    motion: list[dict] = field(default_factory=list)              # per sampled pair global-motion fit
    sharpness: list[float] = field(default_factory=list)          # Laplacian variance of every frame


def noise_sigma(gray: np.ndarray) -> float:
    """Immerkær fast noise estimate (std of additive noise), computed on non-edge pixels."""
    g = gray.astype(np.float32)
    h, w = g.shape
    if h < 8 or w < 8:
        return 0.0
    conv = np.abs(cv2.filter2D(g, -1, _IMMERKAER))[1:-1, 1:-1]
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0)[1:-1, 1:-1]
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)[1:-1, 1:-1]
    mag = np.hypot(gx, gy)
    mask = mag < np.percentile(mag, 60)  # ignore edges/texture, keep smooth areas
    if mask.sum() < 100:
        mask = np.ones_like(mag, dtype=bool)
    return float(math.sqrt(math.pi / 2.0) * conv[mask].mean() / 6.0)


def spatial_features(bgr: np.ndarray) -> dict:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # flat 8x8 blocks
    bh, bw = h // 8, w // 8
    blocks = gray[: bh * 8, : bw * 8].reshape(bh, 8, bw, 8).astype(np.float32)
    bstd = blocks.std(axis=(1, 3))
    flat_ratio = float((bstd < 0.6).mean())
    # low-light split: transcoded night footage crushes shadows into flat near-black blocks, which reads as a
    # "rendered" flat palette. A rendered dark background is one exact colour (std 0); crushed shadows keep grain.
    bmean = blocks.mean(axis=(1, 3))
    dark = bmean < 28
    lit = ~dark
    dark_ratio = float(dark.mean())
    dark_std = float(np.median(bstd[dark])) if dark.any() else 0.0
    dark_flat = float((bstd[dark] < 0.6).mean()) if dark.any() else 0.0
    flat_lit = float((bstd[lit] < 0.6).mean()) if lit.any() else 0.0
    # palette size: number of 4-bit-per-channel colours covering 95% of pixels
    q = (bgr >> 4).astype(np.int32)
    codes = (q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]
    counts = np.bincount(codes.ravel(), minlength=4096)
    counts = np.sort(counts)[::-1]
    cum = np.cumsum(counts) / max(1, counts.sum())
    palette95 = int(np.searchsorted(cum, 0.95) + 1)
    # edges and their orientation
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    strong = mag > 80
    edge_density = float(strong.mean())
    if strong.sum() > 50:
        ang = np.degrees(np.arctan2(gy[strong], gx[strong])) % 90.0
        axis = float(((ang < 4) | (ang > 86)).mean())
    else:
        axis = 0.0
    # what the lit part is made of: shaded surfaces (photo, 3D, AI) have gentle gradients; particles, point clouds,
    # thin lines and small text on black are all fine detail, many small bright peaks per lit pixel
    lit_mask = gray > 50
    n_lit = int(lit_mask.sum())
    gf = gray.astype(np.float32)
    peaks = (gf >= cv2.dilate(gf, np.ones((3, 3), np.uint8))) & (gf - cv2.blur(gf, (7, 7)) > 18) & lit_mask
    # the same on the inverted picture: thin dark lines / dots / small text on a light ground (line art, documents)
    inv = 255 - gray
    ink_mask = inv > 50
    n_ink = int(ink_mask.sum())
    fi = inv.astype(np.float32)
    ink_peaks = (fi >= cv2.dilate(fi, np.ones((3, 3), np.uint8))) & (fi - cv2.blur(fi, (7, 7)) > 18) & ink_mask
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # material texture: cameras, generators and 3D renders put fine texture (fabric, skin, foliage, noise) almost
    # everywhere; vector shapes, gradients, glows and text drawn by code have none. Median-filtered first so a
    # film-grain overlay on a flat design does not count as texture.
    # The detail left after removing the smooth component (high-pass), so smooth gradients and glows count as zero.
    dn = cv2.medianBlur(gray, 5).astype(np.float32)
    hp = dn - cv2.GaussianBlur(dn, (0, 0), 1.5)
    hp_e = np.sqrt(np.maximum(cv2.blur(hp * hp, (5, 5)), 0))
    # gentle slopes (gradients, shading) and whether they curve cleanly (synthetic ramps) or noisily (surfaces)
    slope = (mag > 2) & (mag < 30)
    curv = np.abs(cv2.Laplacian(cv2.GaussianBlur(gf, (0, 0), 1.0), cv2.CV_32F))
    sat, val = hsv[..., 1], hsv[..., 2]
    vivid = (sat > 90) & (val > 60)
    hues = np.bincount((hsv[..., 0][vivid] // 15).ravel(), minlength=12) if vivid.any() else np.zeros(12)
    return {
        "tex_fine": float(((hp_e > 0.6) & (hp_e < 6)).mean()),
        "grad_share": float(slope.mean()),
        "grad_clean": float((curv[slope] < 1.0).mean()) if slope.any() else 0.0,
        "vivid": float(vivid.mean()),
        "hue_n": float((hues / max(1, hues.sum()) > 0.08).sum()),
        "sat_p90": float(np.percentile(sat, 90)) / 255.0,
        "lit_ratio": n_lit / float(h * w),
        "lit_smooth": float(((mag < 40) & lit_mask).sum()) / n_lit if n_lit else 1.0,
        "lit_peaks": 100.0 * float(peaks.sum()) / n_lit if n_lit else 0.0,
        "light_ratio": float((bmean > 227).mean()),
        "ink_ratio": n_ink / float(h * w),
        "ink_smooth": float(((mag < 40) & ink_mask).sum()) / n_ink if n_ink else 1.0,
        "ink_peaks": 100.0 * float(ink_peaks.sum()) / n_ink if n_ink else 0.0,
        "noise_sigma": noise_sigma(gray),
        "flat_ratio": flat_ratio,
        "dark_ratio": dark_ratio,
        "dark_std": dark_std,
        "dark_flat": dark_flat,
        "flat_lit": flat_lit,
        "palette95": palette95,
        "edge_density": edge_density,
        "axis_edge_ratio": axis,
        "saturation": float(hsv[..., 1].mean() / 255.0),
        "luma": float(gray.mean()),
        "contrast": float(gray.std()),
    }


def global_motion(prev: np.ndarray, nxt: np.ndarray) -> dict | None:
    """Fit a similarity transform prev->nxt from tracked corners."""
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=300, qualityLevel=0.01, minDistance=7, blockSize=7)
    if pts is None or len(pts) < 15:
        return None
    nxt_pts, st, _ = cv2.calcOpticalFlowPyrLK(prev, nxt, pts, None, winSize=(21, 21), maxLevel=3)
    back, st2, _ = cv2.calcOpticalFlowPyrLK(nxt, prev, nxt_pts, None, winSize=(21, 21), maxLevel=3)
    if nxt_pts is None or back is None:
        return None
    fb = np.linalg.norm(pts - back, axis=2).ravel()
    ok = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 1.0)
    p0, p1 = pts.reshape(-1, 2)[ok], nxt_pts.reshape(-1, 2)[ok]
    if len(p0) < 12:
        return None
    flow = np.linalg.norm(p1 - p0, axis=1)
    M, _inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=1.0, maxIters=2000)
    if M is None:
        return None
    pred = p0 @ M[:, :2].T + M[:, 2]
    resid = np.linalg.norm(pred - p1, axis=1)
    a, b = float(M[0, 0]), float(M[1, 0])
    # photometric residual after warping prev onto next: a still image being zoomed/panned
    # leaves almost nothing; animated content leaves blocks with real change
    h, w = prev.shape
    warped = cv2.warpAffine(prev, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    mh, mw = int(h * 0.08), int(w * 0.08)
    diff = cv2.absdiff(warped, nxt)[mh:h - mh, mw:w - mw].astype(np.float32)
    bh, bw = diff.shape[0] // 16, diff.shape[1] // 16
    blocks = diff[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16).mean(axis=(1, 3)) if bh and bw else diff
    return {
        "comp_mad": float(diff.mean()),
        "comp_block_p98": float(np.percentile(blocks, 98)),
        "scale": math.hypot(a, b),
        "rot_deg": math.degrees(math.atan2(b, a)),
        "tx": float(M[0, 2]),
        "ty": float(M[1, 2]),
        "flow_median": float(np.median(flow)),
        "flow_p90": float(np.percentile(flow, 90)),
        "resid_median": float(np.median(resid)),
        "inlier_ratio": float((resid < 0.5).mean()),
        "local_ratio": float((resid > 1.5).mean()),
        "n_points": int(len(p0)),
    }


def collect_samples(path: str, info: VideoInfo, shot: Shot, n_frames: int = 16, n_motion: int = 24,
                    crop: tuple[float, float, float, float] | None = None) -> ShotSamples:
    """crop: measure only this part of the frame (0-1 x, y, w, h), e.g. to leave out a sticker / GIF layer."""
    total = shot.end_frame - shot.start_frame
    trim = 2 if total > 12 else 0  # skip frames touching the transition
    lo, hi = trim, max(trim + 1, total - trim)
    usable = hi - lo
    keep = set(np.linspace(lo, hi - 1, num=min(n_frames, usable)).round().astype(int).tolist())
    motion_idx = set(np.linspace(lo + 1, hi - 1, num=min(n_motion, max(usable - 1, 0))).round().astype(int).tolist()) if usable > 1 else set()
    out = ShotSamples()
    prev_gray = None
    for i, bgr in enumerate(iter_frames(path, info, ANALYSIS_W, start=shot.start, duration=shot.duration, crop=crop)):
        if i >= total:
            break
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if lo <= i < hi:
            out.sharpness.append(float(cv2.Laplacian(gray, cv2.CV_32F).var()))
            if i in keep:
                out.frames.append(bgr.copy())
                out.frame_times.append(shot.t(shot.start_frame + i))
            if prev_gray is not None and i - 1 >= lo:
                d = cv2.absdiff(gray, prev_gray)
                out.pair_mad.append(float(d.mean()))
                out.pair_zero.append(float((d == 0).mean()))
                still = d < 6
                out.pair_tnoise.append(float(np.mean(d[still])) if still.any() else 0.0)
                if i in motion_idx:
                    m = global_motion(prev_gray, gray)
                    if m is not None:
                        out.motion.append(m)
        prev_gray = gray
    return out


def _periodicity(flags: list[bool]) -> dict:
    idx = [i for i, f in enumerate(flags) if f]
    if len(idx) < 3:
        return {"period": None, "regularity": 0.0}
    gaps = np.diff(idx)
    vals, cnt = np.unique(gaps, return_counts=True)
    period = int(vals[np.argmax(cnt)])
    regularity = float(cnt.max() / len(gaps))
    return {"period": period, "regularity": regularity}


def shot_features(samples: ShotSamples, fps: float) -> dict:
    sp = [spatial_features(f) for f in samples.frames] or [spatial_features(np.zeros((32, 32, 3), np.uint8))]
    agg = {k: float(np.median([s[k] for s in sp])) for k in sp[0]}
    agg["palette95"] = int(agg["palette95"])

    mad = np.array(samples.pair_mad) if samples.pair_mad else np.zeros(1)
    dup = mad < 0.15
    moving_pairs = mad > 0.6
    per = _periodicity(dup.tolist())
    agg.update({
        "pair_mad_median": float(np.median(mad)),
        "pair_mad_p90": float(np.percentile(mad, 90)),
        "dup_ratio": float(dup.mean()),
        "dup_period": per["period"],
        "dup_regularity": per["regularity"],
        "moving_pair_ratio": float(moving_pairs.mean()),
        "zero_pixel_ratio": float(np.median(samples.pair_zero)) if samples.pair_zero else 0.0,
        "temporal_noise": float(np.median(samples.pair_tnoise)) if samples.pair_tnoise else 0.0,
        "spatial_std_noise": float(np.std([s["noise_sigma"] for s in sp])),
    })
    # change between first and last sampled frame (does the shot evolve at all?)
    if len(samples.frames) >= 2:
        a = cv2.cvtColor(samples.frames[0], cv2.COLOR_BGR2GRAY).astype(np.float32)
        b = cv2.cvtColor(samples.frames[-1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        agg["start_end_mad"] = float(np.abs(a - b).mean())
    else:
        agg["start_end_mad"] = 0.0
    agg.update(resampling_signature(samples.sharpness))
    agg.update(motion_summary(samples.motion, fps))
    return agg


def resampling_signature(sharp: list[float]) -> dict:
    """Frame-rate conversion / interpolation leaves a periodic sharpness pattern (blended or
    synthesized in-between frames are softer). Native camera capture does not."""
    s = np.asarray(sharp, dtype=np.float64)
    if len(s) < 24 or s.mean() <= 0:
        return {"sharp_alt": 0.0, "sharp_period": None, "sharp_period_ac": 0.0}
    alt = float(np.mean(np.abs(s[1:-1] - (s[:-2] + s[2:]) / 2)) / s.mean())
    d = s - np.convolve(s, np.ones(9) / 9, mode="same")
    d = d[5:-5]
    best_lag, best_ac = None, 0.0
    for k in range(2, 7):
        if len(d) > k + 8 and d[:-k].std() > 0 and d[k:].std() > 0:
            ac = float(np.corrcoef(d[:-k], d[k:])[0, 1])
            if ac > best_ac:
                best_lag, best_ac = k, ac
    return {"sharp_alt": alt, "sharp_period": best_lag, "sharp_period_ac": best_ac}


def motion_summary(motion: list[dict], fps: float) -> dict:
    if not motion:
        return {"motion_pairs": 0, "kenburns_score": 0.0, "camera": "unknown"}
    arr = {k: np.array([m[k] for m in motion]) for k in motion[0]}
    zoom_per_s = (np.median(arr["scale"]) - 1.0) * fps
    tx_s, ty_s = np.median(arr["tx"]) * fps, np.median(arr["ty"]) * fps
    speed = float(math.hypot(tx_s, ty_s))
    flow_med = float(np.median(arr["flow_median"]))
    resid = float(np.median(arr["resid_median"]))
    inl = float(np.median(arr["inlier_ratio"]))
    local = float(np.median(arr["local_ratio"]))
    # consistency of per-pair translation: smooth camera -> consistent; handheld -> noisy
    tx, ty = arr["tx"], arr["ty"]
    mag = np.hypot(tx, ty)
    trans_cv = float(np.std(mag) / (np.mean(mag) + 1e-6))
    sign_flips = float((np.sign(tx[1:]) != np.sign(tx[:-1])).mean()) if len(tx) > 2 else 0.0
    moving = abs(zoom_per_s) > 0.004 or speed > 1.5
    # Ken Burns: the entire frame moves as one rigid plane (zoom/pan) with no parallax or local motion
    comp_p98 = float(np.median(arr["comp_block_p98"])) if "comp_block_p98" in arr else 0.0
    kb = 0.0
    if moving and flow_med > 0.08:
        kb = float(np.clip((inl - 0.80) / 0.17, 0, 1) * np.clip((0.35 - resid) / 0.25, 0, 1) * np.clip((0.06 - local) / 0.05, 0, 1)
                   * np.clip(1.2 - trans_cv, 0, 1) ** 0.5 * np.clip((9.0 - comp_p98) / 4.0, 0, 1))
    if flow_med < 0.05 and local < 0.02:
        camera = "static"
    elif not moving:
        camera = "static_with_subject_motion" if local > 0.05 else "static"
    elif kb > 0.5:
        camera = "planar_zoom_pan"
    elif sign_flips > 0.45 and trans_cv > 0.8:
        camera = "handheld_like"
    else:
        camera = "smooth_move"
    return {
        "motion_pairs": len(motion),
        "zoom_per_s": float(zoom_per_s),
        "pan_px_per_s": speed,
        "pan_dir_deg": float(math.degrees(math.atan2(ty_s, tx_s))) if speed > 0 else 0.0,
        "rot_deg_per_s": float(np.median(arr["rot_deg"]) * fps),
        "flow_median": flow_med,
        "flow_p90": float(np.median(arr["flow_p90"])),
        "rigid_inlier_ratio": inl,
        "rigid_residual": resid,
        "local_motion_ratio": local,
        "trans_cv": trans_cv,
        "sign_flip_rate": sign_flips,
        "kenburns_score": kb,
        "comp_block_p98": comp_p98,
        "camera": camera,
    }
