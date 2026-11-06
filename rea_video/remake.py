"""Rebuild a video on the original timeline from remake results.

- generated clips (capsule-cinema)  -> trimmed / padded to the original shot length
- still_motion / static_hold shots  -> rebuilt locally from one image using the measured
                                       zoom/pan (deterministic, no model call)
- everything else                    -> original footage kept (marked in the compare video)
Outputs remake.mp4 (original audio) and compare.mp4 (original | remake side by side)."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import cv2

from .util import LOG, read_json


def _ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def render_still_motion(image: Path, out: Path, duration: float, size: tuple[int, int], fps: float,
                        zoom_per_s: float = 0.0, pan_px_per_s: float = 0.0, pan_dir_deg: float = 0.0,
                        analysis_width: int = 480) -> Path:
    """Re-create a Ken Burns move: per-frame similarity transform about the frame centre,
    with the zoom rate and pan speed measured during decomposition."""
    img = cv2.imread(str(image))
    if img is None:
        raise FileNotFoundError(image)
    w, h = size
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    n = max(1, int(round(duration * fps)))
    px_scale = w / float(analysis_width)
    vx = math.cos(math.radians(pan_dir_deg)) * pan_px_per_s * px_scale
    vy = math.sin(math.radians(pan_dir_deg)) * pan_px_per_s * px_scale
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}",
                             "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)], stdin=subprocess.PIPE)
    assert proc.stdin is not None
    # the measured motion maps frame t -> t+1; start slightly zoomed in when zooming out so edges never show
    base = 1.0 + max(0.0, -zoom_per_s * duration) + 0.02 + (abs(vx) + abs(vy)) * duration / max(w, h)
    for i in range(n):
        t = i / fps
        s = base * (1.0 + zoom_per_s * t)
        M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, s)
        M[0, 2] += vx * t - vx * duration / 2
        M[1, 2] += vy * t - vy * duration / 2
        frame = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return out


def _fit_clip(src: Path, out: Path, duration: float, size: tuple[int, int], fps: float) -> Path:
    w, h = size
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
          f"tpad=stop_mode=clone:stop_duration={duration:.3f},trim=duration={duration:.3f},setpts=PTS-STARTPTS")
    _ff(["-i", str(src), "-an", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)])
    return out


def _original_segment(src: Path, out: Path, start: float, duration: float, size: tuple[int, int], fps: float) -> Path:
    w, h = size
    _ff(["-ss", f"{start:.4f}", "-i", str(src), "-t", f"{duration:.4f}", "-an",
         "-vf", f"scale={w}:{h},fps={fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)])
    return out


def assemble(breakdown_path: Path, results_path: Path, out_dir: Path | None = None) -> str:
    b = read_json(breakdown_path)
    bdir = breakdown_path.parent
    jobs_path = results_path.with_name("jobs.json")
    jobs = {j["shot"]: j for j in read_json(jobs_path)["jobs"]} if jobs_path.is_file() else {}
    results = read_json(results_path).get("results", {}) if results_path.is_file() else {}
    out_dir = out_dir or results_path.parent
    seg_dir = out_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    src = Path(b["source"]["path"])
    w, h = b["source"]["width"], b["source"]["height"]
    if b["source"].get("rotation") in (90, 270):
        w, h = h, w
    w, h = w - w % 2, h - h % 2
    fps = float(b["source"]["fps"]) if b["source"]["fps"] and b["source"]["fps"] <= 60 else 30.0
    parts, legend = [], []
    for sh in b["shots"]:
        dur = sh["duration"]
        seg = seg_dir / f"shot_{int(sh['index']):03d}.mp4"  # 不用 JSON 里的 id 拼路径，防 ../
        res = results.get(str(sh["index"])) or {}
        job = jobs.get(sh["index"], {})
        if res.get("video") and Path(res["video"]).is_file():
            _fit_clip(Path(res["video"]), seg, dur, (w, h), fps)
            legend.append((sh["index"], "generated"))
        elif job.get("executor") == "local_ffmpeg" or sh["base"]["label"] in ("still_motion", "static_hold"):
            m = sh["replication"].get("local", {})
            img = bdir / sh["assets"]["first_frame"]
            render_still_motion(img, seg, dur, (w, h), fps, m.get("zoom_per_s", 0.0), m.get("pan_px_per_s", 0.0),
                                m.get("pan_dir_deg", 0.0), m.get("analysis_width", 480))
            legend.append((sh["index"], "local_still"))
        else:
            _original_segment(src, seg, sh["start"], dur, (w, h), fps)
            legend.append((sh["index"], "original"))
        parts.append(seg)
    lst = seg_dir / "concat.txt"
    lst.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8")
    silent = out_dir / "remake_silent.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
    final = out_dir / "remake.mp4"
    if b["source"].get("has_audio"):
        _ff(["-i", str(silent), "-i", str(src), "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-shortest", str(final)])
    else:
        final = silent
    compare = out_dir / "compare.mp4"
    ch = 720 if h >= 720 else h - h % 2
    label = ",drawtext=text='{t}':x=10:y=10:fontcolor=white:box=1:boxcolor=black@0.5"
    for with_text in (True, False):  # drawtext needs libfreetype; fall back to plain hstack
        la, lb = (label.format(t="original"), label.format(t="remake")) if with_text else ("", "")
        try:
            _ff(["-i", str(src), "-i", str(final), "-filter_complex",
                 f"[0:v]scale=-2:{ch}{la}[a];[1:v]scale=-2:{ch}{lb}[b];[a][b]hstack=inputs=2[v]",
                 "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-shortest", str(compare)])
            break
        except subprocess.CalledProcessError:
            if not with_text:
                raise
    (out_dir / "assemble_log.json").write_text(json.dumps({"legend": legend, "remake": str(final), "compare": str(compare)},
                                                          ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("remake -> %s ; compare -> %s", final, compare)
    return json.dumps({"remake": str(final), "compare": str(compare), "legend": legend}, ensure_ascii=False)
