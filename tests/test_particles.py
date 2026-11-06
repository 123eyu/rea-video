"""Particle / point-cloud graphics on black: rendered by code, not 3D, AI or night footage."""
import cv2
import numpy as np

from rea_video.classify import deterministic
from rea_video.features import spatial_features
from rea_video.plan import code_scene
from rea_video.production import lit_colours, report_md


def _particles(seed=0):
    rng = np.random.default_rng(seed)
    img = np.zeros((270, 480, 3), np.uint8)
    for _ in range(1500):  # glowing dots sampled on an ellipse, like a particle organ
        a = rng.uniform(0, 2 * np.pi)
        r = rng.uniform(0, 1) ** 0.5
        x, y = int(240 + 90 * r * np.cos(a)), int(135 + 60 * r * np.sin(a))
        cv2.circle(img, (x, y), 1, (230, 220, 60), -1)
    return img


def _shaded():
    img = np.zeros((270, 480, 3), np.uint8)
    yy, xx = np.mgrid[0:270, 0:480]
    d = np.sqrt((xx - 240) ** 2 + (yy - 135) ** 2)
    ball = np.clip(255 * (1 - d / 90), 0, 255).astype(np.uint8)  # a smoothly shaded sphere on black
    img[..., 1] = ball
    img[..., 2] = ball
    return img


def _feat(img):
    f = spatial_features(img)
    f.update({"dup_ratio": 0.0, "moving_pair_ratio": 1.0, "camera": "smooth_move", "temporal_noise": 0.5, "zero_pixel_ratio": 0.6})
    return f


def test_fine_dark_separates_particles_from_shaded_surfaces():
    fp, fs = _feat(_particles()), _feat(_shaded())
    assert fp["lit_smooth"] < 0.3 and fp["lit_peaks"] > 4
    assert fs["lit_smooth"] > 0.5
    probs, ev, facts = deterministic(fp)
    assert facts["fine_dark"] > 0.5
    assert max(probs, key=probs.get) == "code_render"
    assert any("粒子" in e for e in ev)
    _, _, facts_s = deterministic(fs)
    assert facts_s["fine_dark"] < 0.1


def test_code_scene_and_report_table(tmp_path):
    cv2.imwrite(str(tmp_path / "a.jpg"), _particles())
    assert lit_colours([tmp_path / "a.jpg"])[0] in ("青", "白")
    shot = {"deterministic": {"facts": {"fine_dark": 0.9}}, "features": {"camera": "smooth_move", "zoom_per_s": 0.05},
            "review": {"description": "青色粒子拼成的胶囊"},
            "text": {"tracks": [{"kind": "subtitle", "texts": ["字幕"]}, {"kind": "title", "texts": ["第一站·胃", "ECOPSWOE"]}],
                     "items": [{"text": "第一站·胃", "conf": 0.99}, {"text": "ECOPSWOE", "conf": 0.55}, {"text": "字幕", "conf": 0.99}]}}
    sc = code_scene(shot)
    assert sc["particles"] and sc["picture"] == "青色粒子拼成的胶囊"
    assert sc["on_screen_text"] == ["第一站·胃"]  # subtitles and low-confidence OCR are left out
    assert "推近" in sc["move"]
    plan = {"summary": "x", "units": [], "shoot": [], "local": [], "avatar": [],
            "code": [{"id": "段1", "shots": [1], "start": 0, "end": 3, "screen_capture": [],
                      "scenes": [{"shot": 1, "start": 0.0, "end": 3.0, **sc, "colours": ["青"]}]}]}
    md = "\n".join(report_md(plan))
    assert "Three.js" in md and "| #1 | 0.0–3.0s | 粒子/点云 | 青色粒子拼成的胶囊 |" in md
