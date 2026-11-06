"""Bridge to capsule-cinema (https://github.com/JuneYaooo/cheap-claude-video).

1. export_capsule_analysis(): converts a rea-video breakdown into the analyzer JSON that
   capsule-cinema's video->capsule pipeline expects (scripts/analyze_video_to_capsule.py),
   so a reusable capsule draft can be produced from an accurate, evidence-backed breakdown.
2. build_remake_jobs(): turns AI-replicable shots (AI video / 3D / live action / avatar)
   into generation jobs for capsule-cinema's UniversalVideoGenerationTool, using the original
   shot's first/last frames and the VLM-derived prompt. Still-image shots are rebuilt locally.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..classify import LABEL_ZH
from ..util import fmt_time, write_json

FORMAT_MAP = {"口播": "short_video", "剧情": "story", "商品展示": "product_showcase", "知识讲解": "explainer",
              "MV": "music_mv", "混剪": "short_video"}
CAMERA_ZH = {"static": "固定机位", "static_with_subject_motion": "固定机位、主体运动", "planar_zoom_pan": "整图推拉/平移",
             "handheld_like": "手持晃动", "smooth_move": "平滑运镜", "unknown": "未知"}
AI_LABELS = ("ai_video", "cg_3d", "live_action", "avatar", "anim_2d", "stop_motion")


def _aspect(b: dict) -> str:
    ar = b["source"].get("aspect_ratio", "unknown")
    return ar if ar in ("9:16", "16:9", "1:1") else "unknown"


TRANS_ZH = {"cut": "硬切", "flash": "闪亮切", "fade": "淡入淡出", "dissolve": "叠化", "mg_transition": "版式切换", "start": "开场"}


def _top_tr(s: dict) -> str:
    tr = {k: v for k, v in s["transitions"].items() if k != "start"} or s["transitions"]
    return max(tr, key=tr.get)


def _mmss(t: float) -> str:
    return fmt_time(t)


def _shot_copy(s: dict) -> str:
    texts = []
    for tr in s.get("text", {}).get("tracks", []):
        if tr["kind"] in ("subtitle", "title"):
            texts += tr["texts"]
    v = s.get("vlm") or {}
    texts += v.get("overlay_text", []) or []
    seen, out = set(), []
    for t in texts:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return " / ".join(out[:6])


def export_capsule_analysis(b: dict, out_path: Path) -> Path:
    s = b["summary"]
    whole = b.get("whole_video_vlm") or {}
    shots = b["shots"]
    mix_txt = "、".join(f"{m['label_zh']} {m['ratio']:.0%}" for m in s["production_mix"])
    segments = []
    literals: list[str] = []
    for sh in shots:
        v = sh.get("vlm") or {}
        f = sh["features"]
        copy = _shot_copy(sh)
        literals += [t for t in copy.split(" / ") if len(t) >= 2]
        motion = CAMERA_ZH.get(f.get("camera", "unknown"), "")
        if sh["base"]["label"] == "still_motion":
            motion += f"；缩放 {f.get('zoom_per_s', 0) * 100:+.1f}%/s，平移 {f.get('pan_px_per_s', 0):.0f}px/s"
        segments.append({
            "start_time": _mmss(sh["start"]), "end_time": _mmss(sh["end"]),
            "beat": f"镜头 {sh['index']}（{sh['duration']:.1f}s）",
            "visuals": f"[{sh['base']['label_zh']} {sh['base']['confidence']:.0%}] " + (v.get("description") or sh["verdict"]),
            "material": (sh.get("material") or {}).get("origin_zh", ""),
            "motion": motion, "copy": copy,
            "audio": "",
            "reuse_lesson": f"该位置用「{LABEL_ZH[sh['base']['label']]}」制作，时长约 {sh['duration']:.1f}s，{motion}",
        })
    # prefer the VLM's narrative beats (with copy/audio) and attach the production method of
    # the shots they overlap; fall back to one segment per shot
    wsegs = [w for w in (whole.get("segments") or []) if isinstance(w, dict)]
    if wsegs:
        merged = []
        for w in wsegs:
            try:
                a, z = float(w.get("start", 0)), float(w.get("end", 0))
            except (TypeError, ValueError):
                continue
            over = [sh for sh in shots if sh["end"] > a and sh["start"] < z] or shots[:1]
            kinds = "、".join(sorted({sh["base"]["label_zh"] for sh in over}))
            merged.append({"start_time": _mmss(a), "end_time": _mmss(z), "beat": str(w.get("beat", "")),
                           "visuals": f"[{kinds}] " + "；".join(((sh.get("vlm") or {}).get("description") or sh["verdict"]) for sh in over[:3]),
                           "motion": "、".join(sorted({CAMERA_ZH.get(sh["features"].get("camera", "unknown"), "") for sh in over})),
                           "copy": str(w.get("copy", "")), "audio": str(w.get("audio", "")),
                           "reuse_lesson": f"这一段（{w.get('beat', '')}）用「{kinds}」实现"})
            if w.get("copy"):
                literals.append(str(w["copy"]))
        if merged:
            segments = merged
    lens = [x["duration"] for x in shots]
    structure_rules = [
        f"全片约 {s['duration']:.0f}s，{s['shots']} 个镜头，平均每镜 {s['avg_shot_s']}s（最短 {min(lens):.1f}s，最长 {max(lens):.1f}s）",
        f"转场以 {TRANS_ZH.get(_top_tr(s), _top_tr(s))} 为主：" + "、".join(f"{TRANS_ZH.get(k, k)}×{v}" for k, v in s["transitions"].items() if k != "start"),
    ]
    if whole.get("hook"):
        structure_rules.append(f"开头钩子：{whole['hook']}")
    visual_rules = [f"底层画面构成：{mix_txt}"]
    for m in s["production_mix"]:
        if m["label"] == "ai_video":
            visual_rules.append("AI 镜头先定首帧（或首尾帧）再生成视频，单镜 4–8 秒，同一角色跨镜头用参考图保持一致")
        if m["label"] == "code_render":
            visual_rules.append("文字、图表、界面类画面用代码/模板渲染，不交给生成模型")
        if m["label"] in ("still_motion", "static_hold"):
            visual_rules.append("部分镜头是静态图（推拉或定格），用图片 + 本地动效即可，不必生成视频")
    rm = s.get("real_material") or {}
    real_inputs: list[str] = []
    if rm.get("shots"):
        kinds = "、".join(rm.get("kinds", {}).keys())
        visual_rules.append(f"引入用户真实素材（{kinds}）：约 {rm['ratio']:.0%} 的时长使用真实截图/照片/实拍，"
                            "这些画面每期需要用户提供新素材，不能用模型生成替代")
        kind_input = {"界面截图": "screenshots", "录屏素材": "screen_recordings", "实拍视频素材": "real_footage",
                      "照片/图片素材": "photos", "真实照片": "photos", "嵌入视频片段": "video_clips", "商品实拍图": "product_photos",
                      "Logo/品牌标识": "brand_logo"}
        real_inputs = sorted({kind_input.get(k, "real_assets") for k in rm.get("kinds", {})})
    styles = sorted({(sh.get("vlm") or {}).get("style", "") for sh in shots} - {""})
    if styles:
        visual_rules.append("画风关键词：" + "；".join(styles[:4]))
    copy_rules = []
    if "subtitle" in s.get("overlay_kinds", []) or (whole.get("subtitles") or {}).get("present"):
        copy_rules.append("字幕由后期代码叠加（不要让模型在画面里生成文字）" + (f"：{whole['subtitles'].get('style')}" if whole.get("subtitles", {}).get("style") else ""))
    if "title" in s.get("overlay_kinds", []):
        copy_rules.append("顶部有固定标题条，全片保持")
    audio_rules = []
    a = b.get("audio", {})
    n = whole.get("narration") or {}
    if n.get("type"):
        audio_rules.append(f"旁白：{n.get('type')} {n.get('voice', '')}".strip())
    elif a.get("speech_likely"):
        audio_rules.append("有人声旁白/对白")
    if (whole.get("music") or {}).get("style"):
        audio_rules.append(f"BGM：{whole['music']['style']}")
    elif a.get("music_likely"):
        audio_rules.append(f"有背景音乐，约 {a.get('tempo_bpm')} BPM")
    if a.get("beat_synced_edit"):
        audio_rules.append("切镜卡在音乐节拍上")
    mu = a.get("music") or {}
    srcs = b.get("sound_sources") or {}
    if srcs.get("music"):
        audio_rules.append(f"BGM 来源：{srcs['music']['source_zh']}（倾向 {srcs['music']['leaning']}）；"
                           + ("MV 类内容：歌是按内容定制的，每期要重新生成歌" if (srcs.get("format_context") or {}).get("music_mv") else "垫底配乐：按风格/BPM 选曲即可"))
    if mu.get("present") and mu.get("tempo_bpm"):
        key = mu.get("key") or {}
        audio_rules.append(f"BGM 约 {mu['tempo_bpm']} BPM" + (f"、{key.get('tonic')} {key.get('mode')}" if key else "")
                           + "；有音高的音效可以对齐 BGM 调性")
    sfx = (b.get("audio_plan") or {}).get("sfx_merged", [])
    if sfx:
        types: dict[str, int] = {}
        for e in sfx:
            types[str(e.get("type", "other"))] = types.get(str(e.get("type", "other")), 0) + 1
        audio_rules.append("音效：" + "、".join(f"{k}×{v}" for k, v in sorted(types.items(), key=lambda kv: -kv[1]))
                           + "，按画面事件（切镜/文字弹出/动作）逐点摆放")
    motion_rules = sorted({CAMERA_ZH.get(sh["features"].get("camera", "unknown"), "") for sh in shots} - {""})
    quality_rules = [
        {"id": "rea_production_mix", "type": "manual_qc_required", "severity": "warning",
         "rule": f"复刻时保持各镜头的制作方式与原片一致（{mix_txt}）"},
        {"id": "rea_ai_artifacts", "type": "manual_qc_required", "severity": "warning",
         "rule": "AI 镜头逐个检查手部、文字、主体形变与闪烁"},
    ]
    content_scope = {
        "schema_version": "capsule.content_scope.v1",
        "series_fixed": ["format_rules", "production_mix", "shot_rhythm", "overlay_style"],
        "episode_variable": ["topic", "subject_facts", "episode_copy", "characters_or_products"] + (["user_supplied_real_assets"] if rm.get("shots") else []),
        "forbidden_reusable_literals": sorted({t.strip() for t in literals if t.strip()}, key=str.casefold)[:80],
        "policies": {"allow_series_fixed_defaults": True, "forbid_episode_specific_defaults": True,
                     "active_recipe_examples_must_use_placeholders": True, "current_run_input_may_reuse_literal": True},
    }
    # de-duplicate case-insensitively (capsule-cinema validator requires it)
    seen, uniq = set(), []
    for t in content_scope["forbidden_reusable_literals"]:
        if t.casefold() not in seen:
            seen.add(t.casefold())
            uniq.append(t)
    content_scope["forbidden_reusable_literals"] = uniq
    fmt = FORMAT_MAP.get(str(whole.get("format", "")), "other" if whole else "short_video")
    data = {
        "summary": whole.get("summary") or s["verdict"],
        "source_profile": {"likely_format": fmt, "aspect_ratio": _aspect(b), "target_platform": "", "primary_audience": ""},
        "segments": segments,
        "capsule_recipe": {
            "when_to_use": ["想复用这条参考视频的镜头节奏、制作方式组合与叠加层风格"],
            "when_not_to_use": ["需要与原片逐帧一致的商业复制（版权/肖像风险）"],
            "structure_rules": structure_rules, "copy_rules": copy_rules, "visual_rules": visual_rules,
            "audio_rules": audio_rules, "motion_rules": motion_rules, "quality_rules": quality_rules,
            "default_runtime": {"aspect_ratio": b["source"].get("aspect_ratio")},
        },
        "execution_strategy": {"mode": "review_required", "reason": "由 rea-video 自动逆向拆解生成，需要人工确认后再固化为配方",
                               "deterministic_steps": [], "parameterized_inputs": ["topic", "reference_images"] + real_inputs,
                               "episode_specific_values": [], "evidence": {"successful_runs": 0, "cross_topic_verified": False}},
        "content_scope": content_scope,
        "warnings": [] if b["analysis"]["vlm"].get("used") else ["未启用 VLM：镜头描述与文案较少，建议用 --vlm 重新拆解"],
        "rea_video": {"verdict": s["verdict"], "production_mix": s["production_mix"], "confidence": s["confidence"],
                      "source": b["source"]["path"]},
    }
    write_json(out_path, data)
    return out_path


def build_remake_jobs(b: dict, bdir: Path, capsule_root: Path, engine: str | None = None,
                      mode: str = "first_last_frame", labels: list[str] | None = None) -> Path:
    """Write jobs.json for `rea-video remake-run` (rea_video/integrations/run_remake.py).
    Output dirs live under <capsule_root>/output/ to satisfy capsule-cinema's output guard.
    engine: overrides the engine planned at decompose time (None keeps the plan's)."""
    from ..plan import CAPSULE_ENGINES

    labels = labels or list(AI_LABELS)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(b["source"]["filename"]).stem)[:40]
    run_dir = capsule_root / "output" / f"rea_remake_{slug}_{stamp}"
    jobs = []
    for sh in b["shots"]:
        lab = sh["base"]["label"]
        rep = sh["replication"]
        if lab in ("still_motion", "static_hold"):
            jobs.append({"shot": sh["index"], "id": sh["id"], "executor": "local_ffmpeg", "label": lab,
                         "image": str((bdir / sh["assets"]["first_frame"]).resolve()), "duration": sh["duration"],
                         "motion": rep.get("local", {}), "user_assets": rep.get("user_assets", [])})
            continue
        if lab not in labels or rep["executor"] != "capsule_cinema":
            jobs.append({"shot": sh["index"], "id": sh["id"], "executor": "keep_original", "label": lab,
                         "reason": rep.get("note", ""), "user_assets": rep.get("user_assets", [])})
            continue
        cap = rep["capsule"]
        gen_type = mode if mode != "first_last_frame" or sh["duration"] >= 1.0 else "image_to_video"
        prompt = cap.get("prompt") or ((sh.get("vlm") or {}).get("description")) or ""
        if not prompt:
            prompt = f"保持参考图的画面、主体与风格，{CAMERA_ZH.get(sh['features'].get('camera', 'unknown'), '')}，自然连贯的动作"
        eng = engine or cap.get("engine") or "seedance2.0"
        gen_dur = cap.get("duration", 5)
        if eng != cap.get("engine"):  # planned for another engine: re-fit the clip length to this one's limits
            lo, hi = CAPSULE_ENGINES.get(eng, (4, 15))
            gen_dur = int(min(hi, max(lo, round(sh["duration"] + 0.49))))
        params = {"prompt": prompt, "output_dir": str(run_dir / sh["id"]), "generation_type": gen_type,
                  "engine": eng, "aspect_ratio": cap.get("aspect_ratio", "9:16"), "duration": gen_dur}
        first = str((bdir / sh["assets"]["first_frame"]).resolve())
        last = str((bdir / sh["assets"]["last_frame"]).resolve())
        if gen_type == "first_last_frame":
            params.update({"start_image_path": first, "end_image_path": last})
        elif gen_type == "image_to_video":
            params["image_path"] = first
        jobs.append({"shot": sh["index"], "id": sh["id"], "executor": "capsule_cinema", "label": lab,
                     "tool": "UniversalVideoGenerationTool", "params": params, "trim_to": sh["duration"],
                     "prompt_source": "vlm" if cap.get("prompt") else "fallback",
                     "user_assets": rep.get("user_assets", []),
                     "warning": "原镜头是真实素材：生成结果只是近似，建议换成你自己的素材" if rep.get("user_assets") else ""})
    out = bdir / "remake" / "jobs.json"
    write_json(out, {"breakdown": str((bdir / "breakdown.json").resolve()), "capsule_root": str(capsule_root),
                     "run_dir": str(run_dir), "engine": engine or b.get("engine") or "seedance2.0", "mode": mode, "jobs": jobs})
    return out
