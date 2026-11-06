from rea_video.classify import deterministic, video_context

PHOTO = {"noise_sigma": 0.5, "temporal_noise": 1.2, "flat_ratio": 0.02, "palette95": 220, "axis_edge_ratio": 0.2,
         "dup_ratio": 0.0, "moving_pair_ratio": 1.0, "zero_pixel_ratio": 0.1, "camera": "smooth_move", "saturation": 0.3}
PROV_WECHAT = {"hints": {"platform": ["WeChat transcode"], "generator": [], "camera": []}}
PROV_DOUYIN = {"hints": {"platform": ["Douyin/TikTok"], "generator": [], "camera": []}}


def _shots(dup):
    return [{"duration": 3.0, "features": dict(PHOTO, dup_ratio=dup)} for _ in range(3)]


def test_video_context_native30_only_without_pulldown():
    assert video_context(_shots(0.0), PROV_WECHAT, 30.0)["native30"] is True
    assert video_context(_shots(0.2), PROV_WECHAT, 30.0)["native30"] is False
    assert video_context(_shots(0.0), PROV_WECHAT, 24.0)["native30"] is False


def test_transcoded_phone_footage_is_not_called_ai():
    ctx = video_context(_shots(0.0), PROV_WECHAT, 30.0)
    probs, ev, facts = deterministic(PHOTO, provenance=PROV_WECHAT, fps=30.0, ctx=ctx)
    assert probs["live_action"] > probs["ai_video"]
    assert facts["transcode_degraded"]


def test_transcoded_ai_with_pulldown_stays_ai():
    f = dict(PHOTO, dup_ratio=0.2, dup_period=5, dup_regularity=0.6)
    ctx = video_context(_shots(0.2), PROV_WECHAT, 30.0)
    probs, _, _ = deterministic(f, provenance=PROV_WECHAT, fps=30.0, ctx=ctx)
    assert probs["ai_video"] > probs["live_action"]


def test_gray_ui_is_not_3d():
    ui = {"noise_sigma": 0.1, "temporal_noise": 0.2, "flat_ratio": 0.65, "palette95": 3, "axis_edge_ratio": 0.27,
          "dup_ratio": 0.2, "moving_pair_ratio": 1.0, "zero_pixel_ratio": 0.9, "saturation": 0.006}
    probs, _, facts = deterministic(ui)
    assert facts["ui_gray"] > 0.5 and probs["code_render"] > probs["cg_3d"]


def test_transcoded_ai_or_live_without_decisive_evidence_is_flagged():
    from rea_video.pipeline import _ai_or_live_doubt

    t = {"transcode_degraded": True, "pulldown": "24→30"}
    assert _ai_or_live_doubt("ai_video", t, {}, {}) and _ai_or_live_doubt("live_action", t, {}, {"native30": False})
    assert _ai_or_live_doubt("ai_video", t, {"aigc": {"label": "1"}}, {}) is None          # AIGC label settles it
    assert _ai_or_live_doubt("live_action", {"transcode_degraded": True}, {}, {"native30": True}) is None  # phone camera
    assert _ai_or_live_doubt("ai_video", {"pulldown": "24→30"}, {}, {}) is None            # not transcoded: noise evidence works
    assert _ai_or_live_doubt("cg_3d", t, {}, {}) is None


def test_native_cadence_is_per_shot():
    # mixed edit: AI opener with 24->30 pulldown, then phone footage without; the whole-file flag is off
    shots = _shots(0.2)[:2] + _shots(0.0)
    ctx = video_context(shots, PROV_DOUYIN, 30.0)
    assert ctx["native30"] is False
    _, _, live = deterministic(dict(PHOTO, noise_sigma=0.4, sharp_period_ac=0.6), provenance=PROV_DOUYIN, fps=30.0, ctx=ctx)
    assert live["native_cadence"] is True  # GOP sharpness rhythm of a re-encode does not count against it
    _, _, ai = deterministic(dict(PHOTO, dup_ratio=0.2, dup_period=5, dup_regularity=0.6), provenance=PROV_DOUYIN, fps=30.0, ctx=ctx)
    assert ai["native_cadence"] is False and ai["pulldown"] == "24→30"
    _, _, f24 = deterministic(PHOTO, provenance=PROV_DOUYIN, fps=24.0, ctx=ctx)
    assert f24["native_cadence"] is False


def test_reviewer_live_call_passes_on_shot_with_camera_cadence():
    from rea_video.pipeline import _ai_or_live_doubt, _vlm_gate

    live = {"live_action": 0.9, "ai_video": 0.1}
    rec = {"deterministic": {"probs": {"ai_video": 0.47, "live_action": 0.39, "cg_3d": 0.1, "avatar": 0.04},
                             "facts": {"transcode_degraded": True, "native_cadence": True, "pulldown": None}},
           "review": {"label_probs": live}}
    assert _vlm_gate(rec, live, {"native30": False}) == live
    rec["deterministic"]["facts"].update(native_cadence=False, pulldown="24→30")
    assert _vlm_gate(rec, live, {"native30": False}) is None
    # and the verdict is not flagged "to confirm" once the shot has cadence and a reader saw filmed footage
    t = {"transcode_degraded": True, "native_cadence": True}
    assert _ai_or_live_doubt("live_action", t, {}, {"native30": False}, seen_live=0.9) is None
    assert _ai_or_live_doubt("live_action", t, {}, {"native30": False}, seen_live=0.0)   # tools alone: still to confirm
    assert "24fps" in _ai_or_live_doubt("live_action", {"transcode_degraded": True, "pulldown": "24→30"}, {}, {"native30": False})


def test_reader_decides_when_tools_are_undecided():
    from rea_video.pipeline import _vlm_gate

    live = {"live_action": 0.9, "ai_video": 0.1}
    facts = {"transcode_degraded": True, "native_cadence": True}
    rec = {"deterministic": {"probs": {"cg_3d": 0.35, "ai_video": 0.27, "live_action": 0.22, "code_render": 0.09}, "facts": facts},
           "review": {"label_probs": live}}
    assert _vlm_gate(rec, live, {"native30": False}) == live          # 3D 0.35 / AI 0.27 / live 0.22 is no call
    rec["deterministic"]["probs"] = {"cg_3d": 0.45, "ai_video": 0.27, "live_action": 0.22, "code_render": 0.06}
    assert _vlm_gate(rec, live, {"native30": False}) is None          # a 0.45 lead is a call: live must be in the top two
    rec["deterministic"]["probs"] = {"cg_3d": 0.35, "ai_video": 0.3, "live_action": 0.12, "code_render": 0.23}
    assert _vlm_gate(rec, live, {"native30": False}) is None          # the reader's pick trails by too much


def test_sharpness_rhythm_alone_is_weak_evidence():
    # a re-encode with its platform tags stripped: no duplicate frames, only a sharpness rhythm
    f = dict(PHOTO, noise_sigma=0.5, sharp_period_ac=0.68, sharp_period=4)
    probs, ev, facts = deterministic(f, provenance={}, fps=30.0, ctx={})
    assert facts["pulldown"] == "interpolated"
    assert not any("重复帧呈" in e or "Duplicate frames follow" in e for e in ev)  # no "duplicate frames" claim at 0%
    dup, _, _ = deterministic(dict(PHOTO, dup_ratio=0.2, dup_period=5, dup_regularity=0.6), provenance={}, fps=30.0, ctx={})
    assert probs["ai_video"] < dup["ai_video"]  # weaker than real 24->30 duplicate frames


def test_reviewer_overrides_sharpness_rhythm_only_call():
    from rea_video.pipeline import _ai_or_live_doubt, _vlm_gate

    live = {"live_action": 0.9, "ai_video": 0.1}
    rec = {"deterministic": {"probs": {"ai_video": 0.86, "live_action": 0.05, "cg_3d": 0.05, "avatar": 0.04},
                             "facts": {"pulldown": "interpolated"}},
           "review": {"label_probs": live}}
    assert _vlm_gate(rec, live, {}) == live
    rec["deterministic"]["facts"]["pulldown"] = "24→30"
    assert _vlm_gate(rec, live, {}) is None  # duplicate-frame pulldown still protects the tools' call
    assert _ai_or_live_doubt("ai_video", {"pulldown": "interpolated"}, {}, {})
    assert _ai_or_live_doubt("ai_video", {"pulldown": "interpolated"}, {"hints": {"generator": ["Kling"]}}, {}) is None


def test_transcoded_native30_shot_counts_as_phone_footage():
    # native 30fps file, this shot has no duplicate frames, platform transcode wiped the noise
    ctx = video_context(_shots(0.0), PROV_DOUYIN, 30.0)
    f = dict(PHOTO, noise_sigma=0.45, temporal_noise=0.5, zero_pixel_ratio=0.6, camera="static")
    probs, _, facts = deterministic(f, provenance=PROV_DOUYIN, fps=30.0, ctx=ctx)
    assert facts["transcode_degraded"] and facts["native_cadence"]
    assert probs["live_action"] > probs["ai_video"]
