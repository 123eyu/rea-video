"""Fusion by group first, real material vs references, scene text, 24p cameras, disputes."""
from rea_video.assets import material_summary
from rea_video.classify import decide, drop_scene_text, fuse
from rea_video.overlay import summarize_text
from rea_video.pipeline import _ai_or_live_doubt, _majority


def test_split_generated_votes_still_beat_live():
    # qing_mv #26: tools say AI video, the agent says avatar / AI video, the VLM says live action
    det = {"live_action": 0.13, "ai_video": 0.44, "avatar": 0.06, "cg_3d": 0.27, "code_render": 0.07, "screen_capture": 0.01,
           "still_motion": 0.01, "static_hold": 0.01}
    seen = {"live_action": 0.475, "ai_video": 0.225, "avatar": 0.243}  # VLM and agent averaged
    rec = {"deterministic": {"probs": det}, "vlm": {"label_probs": {"live_action": 0.95, "ai_video": 0.05}},
           "review": {"label_probs": {"ai_video": 0.4, "avatar": 0.49}}}
    assert _majority(rec) == "ai_video"  # the agent's "avatar" is a vote for the tools' "generated"
    assert decide(fuse(det, seen, "dynamic", majority=_majority(rec)))[0] == "ai_video"
    label, conf = decide(fuse(det, seen, "dynamic"))  # even without the majority rule
    assert label == "ai_video" and conf > 0.55


def test_frozen_constraint_survives_grouping():
    det = {"static_hold": 0.7, "ai_video": 0.2, "avatar": 0.1}
    assert decide(fuse(det, {"ai_video": 0.5, "avatar": 0.3, "static_hold": 0.2}, "frozen"))[0] == "static_hold"


def test_products_in_ai_pictures_are_references():
    vlm = {"embedded_assets": [{"kind": "product_photo", "description": "杯子", "is_real_material": True},
                               {"kind": "logo", "description": "杯身 Logo", "is_real_material": True}]}
    m = material_summary("ai_video", None, [], vlm)
    assert not m["has_real_material"] and m["origin"] == "ai_generated"
    assert [r["kind_zh"] for r in m["references"]] == ["商品参考图", "Logo/品牌参考"]


def test_clip_inside_ui_is_embedded_but_not_called_footage():
    vlm = {"embedded_assets": [{"kind": "real_footage", "description": "播放器里的参考视频", "is_real_material": True}]}
    m = material_summary("code_render", None, [], vlm)
    assert m["has_real_material"] and m["items"][0]["kind_zh"] == "嵌入视频片段" and m["references"] == []


def test_scene_text_dropped_by_vlm_list_and_by_drift():
    layers = [{"kind": "subtitle", "texts": ["mophyrichods", "mophyriohocs"], "drift": None},
              {"kind": "label", "texts": ["这个榨汁杯真的绝了"], "drift": 0.0}]
    keep, dropped = drop_scene_text(layers, "ai_video", ["这个榨汁杯真的绝了"])
    assert [l["texts"][0] for l in keep] == ["这个榨汁杯真的绝了"] and dropped[0] == "mophyrichods"
    keep, _ = drop_scene_text(layers, "code_render", [])  # rendered frames: text is the content, leave it
    assert len(keep) == 2
    # no VLM: words that move across the frame sit on an object
    items = [{"band": "middle", "t": t, "text": "Almond", "angle": 0, "bbox": [0.2 + 0.1 * i, 0.5, 0.2, 0.03]}
             for i, t in enumerate((0.0, 0.5, 1.0))]
    tr = summarize_text(items)["tracks"]
    assert tr[0]["drift"] >= 0.2
    keep, dropped = drop_scene_text([dict(tr[0], texts=tr[0]["texts"])], "live_action", None)
    assert keep == [] and dropped == ["Almond"]


def test_24p_camera_doubt():
    facts = {"pulldown": "24→30", "transcode_degraded": False}
    assert "24p" in _ai_or_live_doubt("ai_video", facts, {}, {}, seen_live=0.8)
    assert _ai_or_live_doubt("ai_video", facts, {}, {}, seen_live=0.1) is None  # a reader looked and saw AI
    assert "看图确认" in _ai_or_live_doubt("ai_video", facts, {}, {}, seen=False)  # nobody looked yet
    assert _ai_or_live_doubt("ai_video", facts, {"hints": {"generator": ["AIGC"]}}, {}, seen=False) is None
    assert _ai_or_live_doubt("ai_video", facts, {"aigc": True}, {}, seen_live=0.8) is None


def test_reader_backing_tools_runner_up_wins_three_way_split():
    det = {"cg_3d": 0.5, "ai_video": 0.2, "live_action": 0.13, "code_render": 0.12, "avatar": 0.02, "screen_capture": 0.01,
           "still_motion": 0.01, "static_hold": 0.01}
    rec = {"deterministic": {"probs": det}, "vlm": {"label_probs": {"live_action": 0.95, "cg_3d": 0.05}},
           "review": {"label_probs": {"ai_video": 0.74, "cg_3d": 0.1, "live_action": 0.06}}}
    assert _majority(rec) == "ai_video"
    seen = {"live_action": 0.5, "ai_video": 0.37, "cg_3d": 0.08}
    assert decide(fuse(det, seen, "dynamic", majority=_majority(rec)))[0] == "ai_video"


def test_agent_review_dispute_flags_ai_live_disagreement():
    # keaton shot_001: tools say ai_video (dark static talking head), the agent review says
    # live action; the fusion follows the tools by design (eval-calibrated), but the
    # disagreement must surface as a dispute flag instead of hiding behind the label
    from rea_video.pipeline import _agent_review_dispute

    note = _agent_review_dispute("ai_video", None, {"live_action": 0.9, "ai_video": 0.05}, False, "fused_agent")
    assert note and "看图复核" in note
    # agreement: no flag
    assert _agent_review_dispute("ai_video", None, {"ai_video": 0.9}, True, "fused_agent") is None
    # an existing VLM answer means the VLM disputed flag owns this case: stay out of it
    assert _agent_review_dispute("ai_video", {"live_action": 0.9}, {"live_action": 0.9}, False, "fused_agent") is None
