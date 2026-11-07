"""Shot boundaries in talking-head and fast-cut edits: jump cuts, brief flashes, very short inserts."""
import cv2
import numpy as np

from rea_video.media import video_info
from rea_video.remake import fit_speed
from rea_video.shots import build_track, detect_shots
from tests.conftest import _photo_like, _write

W, H = 360, 640


def _speaker(bg: np.ndarray, x: int, y: int, t: int, rng) -> np.ndarray:
    """A person in front of a fixed background, swaying slightly from frame to frame."""
    f = bg.copy()
    sway = int(round(3 * np.sin(t / 6)))
    cv2.ellipse(f, (x + sway, y + 360), (130, 220), 0, 180, 360, (40, 40, 50), -1)  # shoulders
    cv2.circle(f, (x + sway, y + 190), 70, (120, 150, 200), -1)  # head
    cv2.circle(f, (x + sway - 25, y + 175), 8, (30, 30, 30), -1)
    cv2.circle(f, (x + sway + 25, y + 175), 8, (30, 30, 30), -1)
    noise = rng.normal(0, 2.0, f.shape)
    return np.clip(f.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def test_jump_cut_found_and_brief_flash_ignored(tmp_path):
    rng = np.random.default_rng(1)
    bg = _photo_like(W, H, 3)
    frames = [_speaker(bg, 180, 160, t, rng) for t in range(45)]
    # jump cut: same camera and background, the speaker is suddenly further left and lower
    frames += [_speaker(bg, 120, 210, t, rng) for t in range(45, 120)]
    for k, gain in ((75, 90.0), (76, 25.0)):  # a two-frame light flash inside the second take
        frames[k] = np.clip(frames[k].astype(np.float32) + gain, 0, 255).astype(np.uint8)
    p = str(_write(frames, tmp_path / "jump.mp4"))
    shots = detect_shots(build_track(p, video_info(p)))
    assert [round(s.start, 2) for s in shots] == [0.0, 1.5]


def test_short_insert_between_two_hard_cuts_is_kept(tmp_path):
    a, b, c = (_photo_like(W, H, s) for s in (11, 12, 13))
    frames = [a] * 30 + [b] * 4 + [c] * 30  # a 4-frame insert, the kind a fast edit or a cover frame makes
    p = str(_write(frames, tmp_path / "insert.mp4"))
    shots = detect_shots(build_track(p, video_info(p)))
    assert [s.start_frame for s in shots] == [0, 30, 34]


def test_generated_clip_is_retimed_to_the_shot():
    assert fit_speed(4.0, 1.25) == 3.0  # a 1.25 s shot from a 4 s minimum generation: whole clip, capped speed-up
    assert abs(fit_speed(5.0, 2.5) - 2.0) < 1e-9
    assert abs(fit_speed(2.0, 4.0) - 0.8) < 1e-9  # too short: slowed a little, the rest held
    assert fit_speed(0.0, 2.0) == 1.0
