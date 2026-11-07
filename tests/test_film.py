import numpy as np

from rea_video.classify import UNMEASURED, deterministic, fuse, group_of, video_context
from rea_video.features import intersect_box, photo_letterbox, picture_box
from rea_video.pipeline import _ai_or_live_doubt, _vlm_gate
from rea_video.production import footage_runs

PHOTO = {"noise_sigma": 0.5, "temporal_noise": 1.2, "flat_ratio": 0.02, "palette95": 220, "axis_edge_ratio": 0.2,
         "dup_ratio": 0.2, "dup_period": 5, "dup_regularity": 0.6, "moving_pair_ratio": 1.0, "zero_pixel_ratio": 0.1,
         "camera": "smooth_move", "saturation": 0.3}


def _letterboxed(seed: int, h: int = 852, w: int = 480, top: int = 300, ph: int = 270) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = np.zeros((h, w, 3), np.uint8)
    f[top:top + ph] = rng.integers(30, 255, (ph, w, 3), dtype=np.uint8)
    f[top - 60:top - 40, 150:330] = 230  # a title line in the top bar
    return f


def test_picture_box_finds_a_film_letterboxed_into_a_vertical_frame():
    frames = [_letterboxed(i) for i in range(4)]
    box = picture_box(frames)
    assert box is not None
    x, y, bw, bh = box["box"]
    assert x == 0 and bw == 1.0 and abs(y - 300 / 852) < 0.01 and abs(bh - 270 / 852) < 0.01
    assert 1.7 < box["aspect"] < 1.85
    assert photo_letterbox(frames) is not None


def test_no_box_on_full_frame_pictures_or_rendered_cards():
    rng = np.random.default_rng(0)
    full = [rng.integers(30, 255, (270, 480, 3), dtype=np.uint8) for _ in range(3)]
    assert picture_box(full) is None
    card = [np.zeros((852, 480, 3), np.uint8) for _ in range(3)]
    for f in card:
        f[300:570] = (40, 120, 220)  # one flat colour: a rendered card, not a film clip
    assert photo_letterbox(card) is None


def test_intersect_box():
    assert intersect_box(None, None) is None
    assert intersect_box((0, 0.3, 1, 0.4), None) == (0, 0.3, 1, 0.4)
    x, y, w, h = intersect_box((0, 0.3, 1, 0.4), (0, 0, 0.8, 1))
    assert (x, y) == (0, 0.3) and abs(w - 0.8) < 1e-9 and abs(h - 0.4) < 1e-9


def test_film_hints_are_evidence_not_a_verdict():
    f = dict(PHOTO, picture_box=[0, 0.35, 1, 0.31], picture_aspect=1.78)
    probs, ev, facts = deterministic(f, fps=30.0)
    assert set(facts["film_hints"]) == {"letterbox", "source_24"}
    assert any("影视片段线索" in e or "Film / TV footage hints" in e for e in ev)
    assert max(probs, key=probs.get) != "film_footage"  # the tools never call it on hints alone
    assert probs["film_footage"] > 0.05


def test_24fps_alone_is_not_a_film_hint():
    _, _, facts = deterministic(PHOTO, fps=30.0)
    assert facts["film_hints"] == []


def test_tool_only_run_flags_film_hints_as_to_confirm():
    f = dict(PHOTO, picture_box=[0, 0.35, 1, 0.31], picture_aspect=1.78)
    _, _, facts = deterministic(f, fps=30.0)
    doubt = _ai_or_live_doubt("ai_video", facts, {}, {}, seen=False)
    assert doubt and ("影视片段" in doubt or "film / TV" in doubt)


def test_film_footage_is_filmed_and_left_to_image_readers():
    assert group_of("film_footage") == "live_action"
    assert "film_footage" in UNMEASURED
    det = {"ai_video": 0.6, "live_action": 0.3, "film_footage": 0.0}
    det = {**{k: 0.01 for k in ("avatar", "cg_3d", "code_render", "screen_capture", "still_motion", "static_hold", "anim_2d", "stop_motion")}, **det}
    rec = {"deterministic": {"probs": det, "facts": {"pulldown": "24→30"}}}
    seen = {"film_footage": 0.85, "ai_video": 0.1, "live_action": 0.05}
    assert _vlm_gate(rec, seen, {}) == seen  # not dropped for missing from the tools' top two
    out = fuse(det, seen, "dynamic")
    assert max(out, key=out.get) == "film_footage"


def test_video_context_film_share():
    shots = [{"duration": 3.0, "features": dict(PHOTO, picture_box=[0, 0.35, 1, 0.31], picture_aspect=1.78)},
             {"duration": 1.0, "features": dict(PHOTO)}]
    assert video_context(shots, None, 30.0)["film_hint_share"] == 0.75


def test_footage_runs_group_contiguous_film_shots():
    def shot(i, label):
        return {"index": i, "start": i, "end": i + 1, "base": {"label": label}}
    runs = footage_runs([shot(1, "film_footage"), shot(2, "film_footage"), shot(3, "live_action"), shot(4, "film_footage")])
    assert [r["shots"] for r in runs] == [[1, 2], [4]]
    assert (runs[0]["start"], runs[0]["end"]) == (1, 3)


def test_reader_picks_film_over_live_action_inside_the_filmed_group():
    det = {k: 0.01 for k in ("avatar", "cg_3d", "code_render", "screen_capture", "still_motion", "static_hold", "anim_2d", "stop_motion")}
    det.update(live_action=0.6, ai_video=0.25, film_footage=0.0)
    out = fuse(det, {"film_footage": 0.85, "live_action": 0.1, "ai_video": 0.05}, "dynamic")
    assert max(out, key=out.get) == "film_footage"
    # and a reader who saw self-shot footage keeps live action
    out = fuse(det, {"live_action": 0.85, "film_footage": 0.1, "ai_video": 0.05}, "dynamic")
    assert max(out, key=out.get) == "live_action"
