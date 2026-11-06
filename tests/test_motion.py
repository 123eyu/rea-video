"""Element motion timeline of code-rendered shots, flash cuts, counters and dark text on light grounds."""
import cv2
import numpy as np

from rea_video.media import video_info
from rea_video.motion import event_line, motion_events, palette
from rea_video.packaging import _NUMERIC, _norm, text_style
from rea_video.shots import build_track, detect_shots


def _close(a, b, tol=6):
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol for i in (1, 3, 5))


def _write(path, frames, fps=30):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    return str(path)


def _staggered(n=90):
    """Three cards pop in 0.5 s apart from 0.2 s, then a bar grows left to right from 1.5 s to 2.5 s."""
    frames = []
    for i in range(n):
        f = np.full((640, 360, 3), (240, 240, 240), np.uint8)
        for k, colour in enumerate([(60, 60, 230), (60, 200, 60), (230, 120, 40)]):
            if i >= 6 + 15 * k:
                cv2.rectangle(f, (40 + 110 * k, 120), (120 + 110 * k, 220), colour, -1)
        if i >= 45:
            w = int(280 * min(1.0, (i - 45) / 30))
            cv2.rectangle(f, (40, 400), (40 + max(1, w), 430), (30, 30, 30), -1)
        frames.append(f)
    return frames


def test_events_time_place_colour(tmp_path):
    p = _write(tmp_path / "s.mp4", _staggered())
    r = motion_events(p, video_info(p), 0.0, 3.0)
    ev = r["events"]
    cards = [e for e in ev if e["box"][1] < 0.4]
    assert len(cards) == 3
    assert [round(e["t0"], 1) for e in cards] == [0.2, 0.7, 1.2]
    assert _close(cards[0]["colour"], "#e63c3c")
    bar = [e for e in ev if e["box"][1] > 0.55]
    assert len(bar) == 1 and bar[0]["sweep"] == "right" and abs(bar[0]["t0"] - 1.5) < 0.15
    assert "向右展开" in event_line(bar[0])
    assert r["sequences"] and r["sequences"][0]["n"] == 3 and abs(r["sequences"][0]["interval"] - 0.5) < 0.1


def test_palette_background():
    f = np.full((200, 100, 3), (231, 241, 246), np.uint8)
    f[80:120, 20:80] = (54, 89, 254)
    pal = palette(f)
    assert _close(pal["background"], "#f6f1e7")
    assert any(_close(c["hex"], "#fe5936") for c in pal["colours"])


def test_flash_cut_and_light_shot_not_a_fade(tmp_path):
    frames = [np.full((360, 200, 3), 20, np.uint8) for _ in range(30)]
    for i in range(30):  # cut into a shot that opens on a grey flash decaying over 0.2 s
        f = np.full((360, 200, 3), 20, np.uint8)
        cv2.circle(f, (100, 180), 40, (200, 200, 60), -1)
        f = cv2.addWeighted(f, 1.0, np.full_like(f, 160), max(0.0, 1 - i / 6), 0)
        frames.append(f)
    for i in range(30):  # hard cut to a white page with a title: a shot, not a fade through white
        f = np.full((360, 200, 3), 255, np.uint8)
        cv2.putText(f, "TITLE", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (40, 40, 40), 2)
        frames.append(f)
    p = _write(tmp_path / "c.mp4", frames)
    shots = detect_shots(build_track(p, video_info(p)))
    assert [round(s.start, 1) for s in shots] == [0.0, 1.0, 2.0]
    assert shots[1].transition_in == "flash" and 0.1 <= shots[1].flash_s <= 0.4
    assert shots[2].transition_in == "cut"


def test_numbers_are_counters_and_dark_text_is_not_outlined():
    assert all(_NUMERIC.fullmatch(_norm(t)) for t in ["820", "4.7%", "12,840", "3.6万", "+4"])
    assert not _NUMERIC.fullmatch(_norm("抖音"))
    f = np.full((120, 400, 3), 255, np.uint8)
    cv2.putText(f, "ABOOD", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (40, 40, 40), 5)
    st = text_style(f, (20, 30, 300, 90), rendered=True)
    assert st and st["fill_name"] in ("黑", "灰") and "stroke" not in st


def test_outlined_subtitle_on_bright_footage_keeps_its_outline():
    """The rendered-picture corrections stay off for footage: white text with a dark outline over a bright scene."""
    f = np.full((120, 400, 3), 235, np.uint8)
    cv2.putText(f, "ABOOD", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (20, 20, 20), 12)
    cv2.putText(f, "ABOOD", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
    st = text_style(f, (14, 26, 310, 94))
    assert st and st["fill_name"] == "白"  # not swapped to dark text, as the rendered rules would on a light ground


def test_element_crops_numbered_like_the_timeline(tmp_path):
    from pathlib import Path

    from rea_video.motion import element_crops

    p = _write(tmp_path / "s.mp4", _staggered())
    info = video_info(p)
    m = motion_events(p, info, 0.0, 3.0)
    sheet = element_crops(p, info, 0.0, 3.0, m, tmp_path / "shots", "shot_001", 360)
    assert sheet == "shots/shot_001_elements.jpg" and (tmp_path / sheet).is_file()
    for k, e in enumerate(m["events"], 1):
        assert e["crop"] == f"shots/shot_001_el_{k:02d}.jpg"
        im = cv2.imread(str(tmp_path / e["crop"]))
        assert im is not None and im.shape[0] > 10
    assert "[截图](shots/shot_001_el_01.jpg)" in event_line(m["events"][0])
    assert Path(tmp_path / "shots").is_dir()


def test_text_style_is_repeatable():
    """Colour clustering must not depend on OpenCV's RNG state (other calls, other threads)."""
    from concurrent.futures import ThreadPoolExecutor

    rng = np.random.default_rng(5)
    f = np.clip(rng.normal(120, 40, (120, 400, 3)), 0, 255).astype(np.uint8)
    cv2.putText(f, "ABOOD", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (30, 30, 200), 9)
    cv2.putText(f, "ABOOD", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (250, 250, 250), 3)

    def run(_):
        cv2.randu(np.zeros((50, 50), np.uint8), 0, 255)  # disturb the RNG
        return text_style(f, (14, 26, 310, 94)), palette(f)

    first = run(0)
    with ThreadPoolExecutor(4) as pool:
        assert all(r == first for r in pool.map(run, range(12)))


def test_style_vote_ties_do_not_depend_on_hash_seed():
    """Python randomises str hashing per process; a tie broken by set order would give different colours per run."""
    import subprocess
    import sys

    code = ("from rea_video.packaging import merge_style;"
            "print(merge_style([{'fill_name':'棕','fill':'#a0522d'},{'fill_name':'橙','fill':'#ff8800'}]))")
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={**__import__("os").environ, "PYTHONHASHSEED": str(seed)}).stdout for seed in range(6)}
    assert len(outs) == 1 and "棕" in outs.pop()
