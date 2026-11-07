"""Human-readable reports from a breakdown: report.md, and report.html rendered from the same Markdown.

Reading order is short-first, long-last: verdict and numbers → what the video says (structure, script) → who / where
(cast) → sound → look and camera → packaging → how to remake it → shot list → open questions → appendix (per-shot
forensics, metadata). Machine-oriented detail (per-shot evidence, measurement tables, 100-row text timelines) is folded
into <details> so it is there when needed and out of the way otherwise. Language: see i18n (breakdown["lang"]).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from . import aspects, entities
from .classify import LABEL_ZH
from .i18n import LangDict, T, join, lang, semi
from .production import report_md as production_md
from .util import fmt_time
from .visual import LABEL_COLOR
from .vlm import vlm_note

KIND_ZH = LangDict({"subtitle": "字幕", "title": "标题", "label": "文字", "static_graphic": "图形贴片", "layout_template": "版式模板",
                    "huazi": "花字", "animated_sticker": "动态贴纸/GIF", "static_sticker": "静态贴纸", "pip": "画中画"},
                   en={"subtitle": "subtitle", "title": "title", "label": "text", "static_graphic": "graphic", "layout_template": "layout template",
                       "huazi": "styled text", "animated_sticker": "animated sticker / GIF", "static_sticker": "static sticker", "pip": "picture-in-picture"})
CAMERA_ZH = LangDict({"static": "固定", "static_with_subject_motion": "固定（主体在动）", "planar_zoom_pan": "整图推拉/平移",
                      "handheld_like": "手持晃动", "smooth_move": "平滑运镜", "unknown": "—"},
                     en={"static": "static", "static_with_subject_motion": "static (subject moves)", "planar_zoom_pan": "whole-frame zoom / pan",
                         "handheld_like": "handheld shake", "smooth_move": "smooth move", "unknown": "—"})
ANIM_ZH = LangDict({"cut": "直接出现", "pop": "弹出", "fade": "淡入", "slide": "滑入", "reveal": "逐字", "cut_out": "直接消失",
                    "pop_out": "缩小消失", "fade_out": "淡出", "slide_out": "滑出"},
                   en={"cut": "hard in", "pop": "pop", "fade": "fade in", "slide": "slide in", "reveal": "type-on", "cut_out": "hard out",
                       "pop_out": "shrink out", "fade_out": "fade out", "slide_out": "slide out"})
GENDER_ZH = LangDict({"male": "偏男声", "female": "偏女声"}, en={"male": "male-leaning", "female": "female-leaning"})
CONF_ZH = LangDict({"medium": "中", "low": "低", "vlm": "VLM 看到"}, en={"medium": "medium", "low": "low", "vlm": "seen by VLM"})
MODE_ZH = LangDict({"music": "背景音乐", "voice": "人声", "sfx": "音效"}, en={"music": "Music", "voice": "Voice", "sfx": "Sound effects"})
# how a shot gets remade, in words (the rule ids stay in breakdown.json for agents)
ROUTE_ZH = LangDict({"ai_video": "AI 生成（首尾帧）", "live_action": "实拍", "avatar": "TTS + 数字人", "cg_3d": "AI 生成 / 3D 渲染",
                     "code_render": "代码渲染", "screen_capture": "录屏重建", "still_motion": "本地 ffmpeg 推拉", "static_hold": "静帧",
                     "anim_2d": "AI 生成（2D 动画）", "stop_motion": "实拍定格", "film_footage": "找原片剪辑"},
                    en={"ai_video": "AI generation (first / last frame)", "live_action": "reshoot", "avatar": "TTS + avatar", "cg_3d": "AI generation / 3D render",
                        "code_render": "code render", "screen_capture": "screen recording", "still_motion": "local ffmpeg move", "static_hold": "static frame",
                        "anim_2d": "AI generation (2D animation)", "stop_motion": "stop motion shoot", "film_footage": "cut from the source film"})
SFX_SRC_ZH = LangDict({"vlm": "听到", "deterministic": "信号候选（低置信）", "review": "看图复核", "merged": "听到 + 信号"},
                      en={"vlm": "heard", "deterministic": "signal candidate (low confidence)", "review": "agent review", "merged": "heard + signal"})
ENDING_ZH = LangDict({"natural_end": "自然结束", "fade_out": "淡出", "hard_cut": "硬切断"}, en={"natural_end": "ends naturally", "fade_out": "fades out", "hard_cut": "cut off hard"})
NARR_ZH = LangDict({"tts": "TTS 合成", "human": "真人", "none": "无", "mixed": "真人 + TTS"}, en={"tts": "TTS", "human": "human", "none": "none", "mixed": "human + TTS"})

_MIX_MARK = "<!--mix-->"
_STEMS_MARK = "<!--stems-->"
_FOLD_ROWS = 12  # tables longer than this are folded into <details>


def _colon() -> str:
    return T("：", ": ")


def _cell(x) -> str:
    return str(x if x not in (None, "") else "—").replace("|", "／").replace("\n", " ")


def _row(*cells) -> str:
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def _table(header: list[str], rows: list[list], fold_title: str | None = None) -> list[str]:
    """A Markdown table; long ones are folded behind a <details> with `fold_title`."""
    if not rows:
        return []
    L = [_row(*header), "|" + "---|" * len(header)] + [_row(*r) for r in rows]
    if fold_title and len(rows) > _FOLD_ROWS:
        return ["", f"<details><summary>{html.escape(fold_title)}</summary>", ""] + L + ["", "</details>"]
    return [""] + L


def _shots_str(ids) -> str:
    return join(f"#{i}" for i in ids) if ids else "—"


def _layers(rec: dict) -> str:
    ks = []
    for l in rec.get("layers", []):
        k = KIND_ZH.get(l["kind"], l["kind"])
        if k not in ks:
            ks.append(k)
    return join(ks) or "—"


def _origin(rec: dict) -> str:
    m = rec.get("material") or {}
    if not m:
        return "—"
    kinds = []
    for it in m.get("items", []):
        if it.get("real_material") and it["kind_zh"] not in kinds:
            kinds.append(it["kind_zh"])
    unsure = sorted({it["kind_zh"] for it in m.get("items", []) if it.get("real_material") is None})
    refs = list(dict.fromkeys(x["kind_zh"] for x in m.get("references", [])))
    return (m.get("origin_zh", "—") + (f"{_colon()}{join(kinds)}" if kinds else "")
            + (semi() + T("待确认是否真实：", "real or not, to confirm: ") + join(unsure) if unsure else "")
            + (semi() + T("复刻参考：", "references for the remake: ") + join(refs) if refs else ""))


def _decided_by(b: dict) -> str:
    if b["analysis"]["vlm"].get("used"):
        return T("确定性取证 + VLM 融合", "deterministic forensics + VLM")
    if (b["analysis"].get("review") or {}).get("shots"):
        return T("确定性取证 + agent 看图融合", "deterministic forensics + agent image review")
    return T("仅确定性取证", "deterministic forensics only")


def _unit_of(b: dict) -> dict[int, str]:
    """shot index -> generation unit / shooting scene / code project id from the production plan."""
    plan = b.get("production_plan") or {}
    out: dict[int, str] = {}
    for u in plan.get("units", []):
        for i in u["shots"]:
            out[i] = u["id"]
    for s in plan.get("shoot", []):
        for i in s["shots"]:
            out[i] = s["id"]
    for c in plan.get("code", []):
        for i in c["shots"]:
            out[i] = c["id"]
    return out


def _route(r: dict, units: dict[int, str]) -> str:
    base = ROUTE_ZH.get(r["base"]["label"], r["replication"].get("executor", ""))
    u = units.get(r["index"])
    return f"{base} · {u}" if u else base


def _t(x) -> str:
    try:
        return f"{float(x):.1f}s"
    except (TypeError, ValueError):
        return "—"


def _span(a, z) -> str:
    try:
        return f"{float(a):.1f}–{float(z):.1f}s"
    except (TypeError, ValueError):
        return "—"


# ------------------------------------------------------------------ sections --------------------------------------

TRANS_ZH = LangDict({"cut": "硬切", "jump": "跳剪", "flash": "闪亮切", "fade": "淡入淡出", "dissolve": "叠化", "mg_transition": "版式切换"},
                    en={"cut": "cut", "jump": "jump cut", "flash": "flash cut", "fade": "fade", "dissolve": "dissolve", "mg_transition": "layout change"})


def _head_md(b: dict) -> list[str]:
    s, src = b["summary"], b["source"]
    L = [T("# 视频拆解报告：{f}", "# Video breakdown: {f}", f=src["filename"]), "",
         T("**结论**：{v}", "**Verdict**: {v}", v=s["verdict"]), "",
         T("- 时长 {d}s · {w}×{h} · {fps}fps · {ar}；镜头 {n} 个，平均 {avg}s；转场：", "- {d}s · {w}×{h} · {fps}fps · {ar}; {n} shots, {avg}s average; transitions: ",
           d=src["duration"], w=src["width"], h=src["height"], fps=src["fps"], ar=src["aspect_ratio"], n=s["shots"], avg=s["avg_shot_s"])
         + (join(f"{TRANS_ZH[k] if k in TRANS_ZH else k}×{v}" for k, v in s["transitions"].items() if k != "start") or "—"),
         T("- 判断置信度（按时长加权）{c:.0%}；判定方式：{by}；{vlm}", "- Confidence (duration-weighted) {c:.0%}; decided by: {by}; {vlm}",
           c=s["confidence"], by=_decided_by(b), vlm=s.get("vlm") or vlm_note(b["analysis"]["vlm"], b["analysis"].get("review")))]
    if s.get("production"):
        L.append(T("- 复刻：{p}（方案见「复刻方案」）", "- Remake: {p} (see “Remake plan”)", p=s["production"]))
    qs = entities.open_questions(b)
    if qs:
        L.append(T("- ⚠️ 待确认 {n} 处，先看「不确定点」：{q}", "- ⚠️ {n} open questions, see “Open questions” first: {q}", n=len(qs),
                   q=qs[0][:80] + ("…" if len(qs[0]) > 80 else "")))
    L += ["", _MIX_MARK] + _table([T("底层画面", "Base picture"), T("时长", "Duration"), T("占比", "Share")],
                                   [[m["label_zh"], f"{m['seconds']}s", f"{m['ratio']:.0%}"] for m in s["production_mix"]])
    L += ["", "![storyboard](storyboard.jpg)"]
    return L


def _content_md(b: dict) -> list[str]:
    w = b.get("whole_video_vlm") or {}
    lines = entities.script(b)
    L = ["", T("## 内容与结构", "## Content and structure"), ""]
    if not w and not lines:
        L.append(T("- 没有整片的内容概括（需要 VLM 或 agent 看完整片）；字幕原文见「剪辑包装层」",
                   "- No whole-video summary (needs the VLM or an agent watching the full video); subtitle text is under “Packaging layer”"))
        return L
    if w.get("summary"):
        L.append(T("- 概括：{s}", "- Summary: {s}", s=w["summary"]))
    bits = []
    if w.get("format"):
        bits.append(T("形式：{f}", "format: {f}", f=w["format"]))
    if w.get("hook"):
        bits.append(T("钩子：{h}", "hook: {h}", h=w["hook"]))
    if bits:
        L.append("- " + semi().join(bits))
    if w.get("overall_production"):
        L.append(T("- 整体制作：{o}", "- Overall production: {o}", o=w["overall_production"]))
    segs = [sg for sg in (w.get("segments") or []) if isinstance(sg, dict)][:30]
    if segs:
        L += ["", T("**结构时间轴**", "**Structure**")]
        L += _table([T("时间", "Time"), T("这一段在做什么", "Beat"), T("文案", "Copy"), T("声音", "Audio")],
                    [[_span(sg.get("start"), sg.get("end")), sg.get("beat", ""), sg.get("copy", ""), sg.get("audio", "")] for sg in segs])
    if lines:
        n = w.get("narration") or {}
        head = T("**脚本**", "**Script**")
        if n.get("type") and n.get("type") != "none":
            head += T("（{t}{v}）", " ({t}{v})", t=NARR_ZH.get(n["type"], n["type"]), v=(T("，", ", ") + n["voice"]) if n.get("voice") else "")
        L += ["", head]
        L += _table([T("时间", "Time"), T("谁", "Who"), T("台词 / 旁白", "Line")],
                    [[_span(ln["start"], ln["end"]), ln["speaker"] or T("旁白", "narration"), ln["text"]] for ln in lines], fold_title=T("全部 {n} 句", "all {n} lines", n=len(lines)))
    return L


def _cast_md(b: dict) -> list[str]:
    c = entities.cast(b)
    L = ["", T("## 角色、场景与道具", "## Cast, scenes and props"), ""]
    if c["characters"]:
        L.append(T("复刻时每个角色固定一张参考图（`@图片`）贯穿所有生成单元，外观按下表写进首帧提示词，角色才不会一镜一个样。",
                   "For the remake, give every character one reference image (`@image`) used across all generation units and copy the look below into the first-frame prompts, so the character stays the same from shot to shot."))
        L += _table([T("编号", "Id"), T("称呼", "Name"), T("类型", "Kind"), T("外观", "Look"), T("作用", "Role"), T("声音", "Voice"), T("出场", "Shots")],
                    [[ch["id"], ch["name"], entities.KIND_ZH.get(ch["kind"], ch["kind"]), ch["look"], ch["role"], ch["voice"], _shots_str(ch["shots"])] for ch in c["characters"]])
    else:
        L.append(T("- 没有归纳出角色（需要 VLM 整片分析，或 agent 看图后在 `review_answers.json` 顶层 `cast` 里填）",
                   "- No cast extracted (needs the VLM whole-video pass, or an agent filling top-level `cast` in `review_answers.json`)")
                 + (T("；人脸检测器在这些镜头看到脸（真人或角色）：{s}", "; shots where the face detector saw a face (person or character): {s}", s=_shots_str(c["face_shots"])) if c["face_shots"] else ""))
    if c["scenes"]:
        L += ["", T("**场景**", "**Scenes**")]
        L += _table([T("场景", "Scene"), T("地点", "Where"), T("时间", "When"), T("布景 / 光线", "Set / light"), T("镜头", "Shots")],
                    [[sc["id"], sc["where"], sc["when"], sc["look"], _shots_str(sc["shots"])] for sc in c["scenes"]])
    if c["props"]:
        L += ["", T("**道具 / 商品 / Logo**", "**Props / products / logos**"), ""]
        for p in c["props"]:
            L.append(f"- {p['name']}" + (T("（镜头 {s}）", " (shots {s})", s=_shots_str(p["shots"])) if p["shots"] else "") + (f"{_colon()}{p['note']}" if p.get("note") else ""))
    return L


def _audio_md(b: dict) -> list[str]:
    a = b.get("audio", {})
    L = ["", T("## 声音", "## Sound"), ""]
    if not a.get("has_audio"):
        L.append(T("- 没有音轨", "- No audio track"))
        return L
    w = b.get("whole_video_vlm") or {}
    src = b.get("sound_sources") or {}
    tracks = {t["track"]: t for t in (b.get("audio_plan") or {}).get("plan", [])}
    L.append("![audio](audio.png)")
    L.append("")
    over = [T("响度 {r} dBFS，峰值 {p} dBFS", "loudness {r} dBFS, peak {p} dBFS", r=a.get("rms_dbfs"), p=a.get("peak_dbfs"))]
    if w.get("mix"):
        over.append(T("混音：{m}", "mix: {m}", m=w["mix"]))
    pc = b.get("per_clip_audio") or {}
    if pc.get("ratio") is not None:
        over.append(T("每段画面自带声音（切点处背景声跳变 {a}dB，镜头内 {w}dB）", "each clip carries its own sound (background jumps {a}dB at cuts vs {w}dB within shots)", a=pc["at_cuts_db"], w=pc["within_shots_db"])
                    if pc.get("resets_at_cuts") else
                    T("声音跨切点连续，是后期整体铺的（切点处背景声变化 {a}dB，镜头内 {w}dB）", "sound runs across cuts, laid in post as one bed (background changes {a}dB at cuts vs {w}dB within shots)", a=pc["at_cuts_db"], w=pc["within_shots_db"]))
    L.append("- " + semi().join(over))
    if src.get("summary_zh"):
        L.append(T("- 来源判断：{s}", "- Sources: {s}", s=src["summary_zh"]))

    def _source_lines(k: str) -> list[str]:
        v = src.get(k) or {}
        if not v:
            return []
        probs = T("，", ", ").join(f"{kk} {vv:.0%}" for kk, vv in sorted(v["probs"].items(), key=lambda kv: -kv[1])[:3])
        out = [T("- 来源：{s}（{p}）", "- Source: {s} ({p})", s=v["source_zh"], p=probs)]
        out += [f"  - {e}" for e in v.get("evidence", [])[:4]]
        out += [T("  - 确认方法：{h}", "  - How to confirm: {h}", h=h) for h in v.get("how_to_confirm", [])[:2]]
        return out

    # voice
    v = a.get("voice", {})
    n = w.get("narration") or {}
    L += ["", T("**人声**", "**Voice**"), ""]
    if v.get("present"):
        bits = [T("占 {r:.0%} 时长", "{r:.0%} of the duration", r=v.get("ratio", 0))]
        if n.get("type") and n["type"] != "none":
            bits.append(NARR_ZH.get(n["type"], n["type"]) + (T("，{v}", ", {v}", v=n["voice"]) if n.get("voice") else "") + (T("，{s}", ", {s}", s=n["style"]) if n.get("style") else ""))
        if v.get("f0_median_hz"):
            bits.append(T("基频约 {f}Hz（{g}）", "pitch about {f}Hz ({g})", f=v["f0_median_hz"], g=GENDER_ZH.get(v.get("gender_hint"), T("性别不确定", "gender unclear"))))
        if v.get("sung"):
            bits.append(T("是唱的", "sung"))
        L.append("- " + semi().join(bits))
        L += _source_lines("voice")
        if tracks.get("voice"):
            L.append(T("- 复刻：{h}", "- Remake: {h}", h=tracks["voice"]["how"]))
        if entities.script(b):
            L.append(T("- 台词见「内容与结构」的脚本表", "- Lines are in the script table under “Content and structure”"))
    else:
        L.append(T("- 无 / 很少", "- None / very little"))

    # music
    mu = a.get("music", {})
    vm = w.get("music") or {}
    L += ["", T("**背景音乐**", "**Music**"), ""]
    if mu.get("present") or vm.get("present"):
        if vm.get("song_guess"):
            L.append(T("- 歌曲：{s}", "- Song: {s}", s=vm["song_guess"]))
        desc = [x for x in (vm.get("style"), vm.get("genre"), vm.get("mood")) if x]
        if vm.get("instruments"):
            desc.append(join(vm["instruments"][:5]))
        if vm.get("has_vocals") is not None:
            desc.append(T("有人声演唱", "with vocals") if vm.get("has_vocals") else T("纯音乐", "instrumental"))
        if desc:
            L.append(T("- 风格：", "- Style: ") + semi().join(desc))
        if vm.get("lyrics_excerpt"):
            L.append(T("- 歌词：{l}", "- Lyrics: {l}", l=str(vm["lyrics_excerpt"])[:120])
                     + (T("（唱的就是画面内容）", " (the lyrics describe the video itself)") if vm.get("lyrics_match_content") else ""))
        tempo = []
        if mu.get("tempo_bpm"):
            tempo.append(T("{bpm} BPM（也可能是 {alt}）", "{bpm} BPM (or {alt})", bpm=mu["tempo_bpm"], alt="/".join(str(t) for t in mu.get("tempo_alternatives", []))) if mu.get("tempo_alternatives")
                         else f"{mu['tempo_bpm']} BPM")
        key = mu.get("key") or {}
        if key:
            tempo.append(T("调性 {t} {m}（置信 {c}）", "key {t} {m} (confidence {c})", t=key.get("tonic"), m=key.get("mode"), c=key.get("confidence")))
        if mu.get("present"):
            tempo.append(T("占 {r:.0%} 时长（{s}–{e}s）", "{r:.0%} of the duration ({s}–{e}s)", r=mu.get("ratio", 0), s=mu.get("start"), e=mu.get("end")))
        if mu.get("section_changes"):
            tempo.append(T("段落变化点 {p}", "section changes at {p}", p=", ".join(str(t) + "s" for t in mu["section_changes"][:8])))
        ending = vm.get("ending") or (src.get("music") or {}).get("ending")
        if ending:
            tempo.append(T("片尾{e}", "ending: {e}", e=ENDING_ZH.get(ending, ending)))
        if tempo:
            L.append(T("- 节奏：", "- Tempo: ") + semi().join(tempo))
        if "cuts_on_beat_ratio" in a:
            L.append(T("- 剪辑与节拍：{r:.0%} 的切点落在节拍上（随机约 {c:.0%}）", "- Cuts vs beat: {r:.0%} of cuts land on a beat (chance: about {c:.0%})",
                       r=a["cuts_on_beat_ratio"], c=a["cuts_on_beat_chance"]) + (T(" → **卡点剪辑**", " → **beat-synced edit**") if a.get("beat_synced_edit") else ""))
        L += _source_lines("music")
        if tracks.get("music"):
            L.append(T("- 复刻：{h}", "- Remake: {h}", h=tracks["music"]["how"]))
    else:
        L.append(T("- 未检测到持续的音乐床", "- No sustained music bed detected"))

    # sfx
    sfx = (b.get("audio_plan") or {}).get("sfx_merged", [])
    L += ["", T("**音效**", "**Sound effects**") + (f"（{len(sfx)}）" if sfx and lang() == "zh" else (f" ({len(sfx)})" if sfx else "")), ""]
    if sfx:
        rows = []
        for e in sfx[:60]:
            on = (e.get("on") or {}).get("what") or e.get("sync_with", T("切点", "cut") if e.get("sync_with_visual") else "")
            rows.append([f"{float(e.get('t', 0)):.2f}s", e.get("type", ""), e.get("description", "") or e.get("anchor", ""), on, SFX_SRC_ZH.get(e.get("source"), e.get("source", ""))])
        L += _table([T("时间", "Time"), T("类型", "Type"), T("描述", "Description"), T("对应画面", "On screen"), T("依据", "Basis")], rows, fold_title=T("全部 {n} 处音效", "all {n} sound effects", n=len(rows)))
        L.append("")
        L += _source_lines("sfx")
        if tracks.get("sfx"):
            L.append(T("- 复刻：{h}", "- Remake: {h}", h=tracks["sfx"]["how"]))
    else:
        L.append(T("- 信号层面未检出显著音效（人声和音乐下面的轻音效需要 VLM 听，见 --vlm）",
                   "- Nothing prominent at the signal level (quiet effects under voice and music need the VLM, see --vlm)"))

    # ambience + files
    amb = w.get("ambience") or (tracks.get("ambience") or {}).get("what")
    if amb or tracks.get("ambience"):
        L += ["", T("**环境声**", "**Ambience**"), "", f"- {amb or '—'}" + (T("；复刻：{h}", "; remake: {h}", h=tracks["ambience"]["how"]) if tracks.get("ambience") else "")]
    st = b.get("stems") or {}
    if st.get("ok"):
        L += ["", T("- 分离出的音轨：`stems/original.wav`（原声）、`stems/vocals.wav`（人声干声，瞬态音效也会落在这里）、`stems/music.wav`（配乐 + 环境声）",
                    "- Separated stems: `stems/original.wav` (original), `stems/vocals.wav` (dry voice; transient sound effects land here too), `stems/music.wav` (music + ambience)"),
              _STEMS_MARK]
    if (b.get("audio_plan") or {}).get("mix"):
        L.append(T("- 混音复刻：{m}", "- Mix for the remake: {m}", m=b["audio_plan"]["mix"]))
    return L


def _visual_md(b: dict) -> list[str]:
    style = entities.cast(b).get("style")
    L = aspects.report_md(b)
    if not L and not style:
        return []
    if not L:
        L = ["", T("## 拍法、打光与剪辑", "## Camera, lighting and editing"), ""]
    if style:
        L.insert(3, T("- 视觉风格：{s}", "- Visual style: {s}", s=style))
    return L


def packaging_md(b: dict) -> list[str]:
    """剪辑包装层: subtitles / 花字 / titles / labels / stickers and the sound effects that land on them."""
    pack = b.get("packaging")
    if not pack:
        return []
    cues = [c for c in pack.get("text_cues", []) if c["kind"] != "scene" and not c.get("part_of_picture")]
    stickers = [st for st in pack.get("stickers", []) if not st.get("in_picture")]
    L = ["", T("## 剪辑包装层（字幕 / 花字 / 贴纸 / 音效卡点）", "## Packaging layer (subtitles / styled text / stickers / sound-effect hits)"), ""]
    for line in pack.get("summary_zh") or []:
        L.append(f"- {line}")
    if not cues and not stickers:
        L.append(T("- 没有检出后期叠加的文字或贴纸", "- No overlaid text or stickers detected")
                 + (T("（未开 OCR，文字层没有分析）", " (OCR off, text layer not analysed)") if not (b.get("analysis") or {}).get("ocr", True) else ""))
    files = pack.get("files") or {}
    if files:
        L.append(T("- 导出：", "- Exports: ") + join(f"`{v}`" for v in files.values())
                 + T("（SRT 是字幕时间轴；ASS 带颜色、描边、位置和入场动画，字体需要换成原片字体；timeline.json 是完整时间轴）",
                     " (SRT is the subtitle timeline; ASS carries colour, outline, position and entrance animation, swap in the original font; timeline.json is the full timeline)"))
    if cues:
        sfx_by_ref: dict[str, list[str]] = {}
        for e in (b.get("audio_plan") or {}).get("sfx_merged", []):
            ref = (e.get("on") or {}).get("ref")
            if ref:
                sfx_by_ref.setdefault(ref, []).append(str(e.get("type", "")))
        rows = []
        for c in sorted(cues, key=lambda c: c["t0"])[:120]:
            anim = " / ".join(x for x in (ANIM_ZH.get((c.get("anim_in") or {}).get("kind"), ""), ANIM_ZH.get((c.get("anim_out") or {}).get("kind"), "")) if x)
            if c.get("mid_motion"):
                anim += T("（中途有弹跳/变色）", " (bounces / changes colour midway)")
            kind = c["kind_zh"] + (T("·跟随物体", " · follows an object") if c.get("follows") else "")
            rows.append([f"{c['t0']:.2f}–{c['t1']:.2f}s", kind, c["text"].replace("/", " ⏎ ")[:40], c.get("style_zh", ""), anim or "—", join(sfx_by_ref.get(c["id"], [])) or "—"])
        L += _table([T("时间", "Time"), T("类型", "Kind"), T("文字", "Text"), T("样式", "Style"), T("入场 / 出场", "In / out"), T("音效", "SFX")], rows,
                    fold_title=T("文字时间轴（{n} 条）", "text timeline ({n} rows)", n=len(rows)))
    if stickers:
        rows = []
        for st in stickers:
            where = (T("x{0:.0%} y{1:.0%} 宽{2:.0%} 高{3:.0%}", "x{0:.0%} y{1:.0%} w{2:.0%} h{3:.0%}").format(*st["bbox"]) if st.get("bbox") else (st.get("where") or "—"))
            dyn = (T("循环，周期 {p:.2f}s", "loops every {p:.2f}s", p=st["loop_period_s"]) if st.get("looping")
                   else (T("在动", "animated") if st.get("animated") else T("静止", "static")))
            why = []
            if st.get("crosses_cut"):
                why.append(T("跨切镜不变", "unchanged across a cut"))
            if st.get("disappears_mid_shot"):
                why.append(T("镜头中途出现又消失", "appears and disappears mid-shot"))
            conf = CONF_ZH.get(st.get("confidence"), st.get("confidence", "")) + (("（" + join(why) + "）") if why else "")
            rows.append([f"{st['t0']:.2f}–{st['t1']:.2f}s", st["kind_zh"], where, dyn, conf, f"![{st['id']}]({st['image']})" if st.get("image") else "—"])
        L += ["", T("**贴纸 / 动图 / 画中画**", "**Stickers / GIFs / picture-in-picture**")]
        L += _table([T("时间", "Time"), T("类型", "Kind"), T("位置", "Position"), T("动态", "Motion"), T("置信", "Confidence"), T("截图", "Crop")], rows)
        dropped = [st for st in pack.get("stickers", []) if st.get("in_picture")]
        if dropped:
            L.append(T("- 另有 {n} 处画面里突然出现的东西没算作贴纸（3D/动画/版式画面里元素本来就会出现）",
                       "- {n} more things that pop up in the picture were not counted as stickers (elements appear on their own in 3D / animation / layout shots)", n=len(dropped)))
    if pack.get("vlm_text_effects"):
        fx = pack["vlm_text_effects"][:20]
        L += ["", f"<details><summary>{html.escape(T('VLM 看到的文字特效（{n}）', 'Text effects seen by the VLM ({n})', n=len(fx)))}</summary>", ""]
        for e in fx:
            L.append(f"- {e.get('t', '')}s {e.get('kind', '')}「{e.get('text', '')}」{e.get('style', '')} {e.get('animation', '')}")
        L += ["", "</details>"]
    L += ["", T("复刻：字幕和花字用 `packaging/overlays.ass` 直接压制（ffmpeg -vf ass=overlays.ass），或按 timeline.json 在剪映 / Remotion 里重建；"
                "贴纸和动图要找同款素材（表情包库 / GIF 库），截图在 packaging/ 下。",
                "Remake: burn subtitles and styled text in with `packaging/overlays.ass` (ffmpeg -vf ass=overlays.ass), or rebuild them from timeline.json in CapCut / Remotion; "
                "stickers and GIFs need matching assets (meme / GIF libraries), crops are under packaging/.")]
    return L


def _remake_md(b: dict) -> list[str]:
    s = b["summary"]
    L = production_md(b.get("production_plan") or {})
    if not L:
        L = ["", T("## 复刻方案", "## Remake plan"), ""]
    rm = s.get("real_material") or {}
    if rm.get("shots"):
        L += ["", T("### 画面里的真实素材（必须拿到原文件）", "### Real material in the picture (the original files are needed)"), "",
              T("共 {n} 个镜头、{s}s（{r:.0%}）的画面里有真实素材（录屏、截图、照片、嵌入视频），模型生成替代不了：",
                "{n} shots, {s}s ({r:.0%}) contain real material (screen recordings, screenshots, photos, embedded video); a model cannot stand in for them:",
                n=len(rm["shots"]), s=rm["seconds"], r=rm["ratio"]), ""]
        for r in b["shots"]:
            for a in r.get("replication", {}).get("user_assets", []):
                L.append(T("- 镜头 #{i}（{t}）：{k}，{w}", "- Shot #{i} ({t}): {k}, {w}", i=r["index"], t=fmt_time(r["start"]), k=a["kind_zh"], w=a["where"])
                         + (f"{T('，', ', ')}{a['description']}" if a.get("description") else ""))
    if s.get("references"):
        L += ["", T("### 复刻要准备的参考素材", "### Reference material to prepare for the remake"), "",
              T("这些镜头的画面是生成或拍摄出来的，下面是画面里出现、复刻时应作为参考图 / 道具准备的东西（不是嵌入的真实像素）：",
                "These shots were generated or filmed; the items below appear in them and should be prepared as reference images / props for the remake (they are not embedded real pixels):"), ""]
        for r in b["shots"]:
            for a in (r.get("material") or {}).get("references", []):
                L.append(T("- 镜头 #{i}（{t}）：{k}", "- Shot #{i} ({t}): {k}", i=r["index"], t=fmt_time(r["start"]), k=a["kind_zh"])
                         + (f"{T('，', ', ')}{a['description']}" if a.get("description") else ""))
    return L


def _shotlist_md(b: dict) -> list[str]:
    units = _unit_of(b)
    rows = []
    for r in b["shots"]:
        base = r["base"]
        desc = ((r.get("vlm") or r.get("review") or {}).get("description") or "").replace("\n", " ")
        rows.append([r["index"], fmt_time(r["start"]), f"{r['duration']:.2f}s", f"{base['label_zh']} {base['confidence']:.0%}", _origin(r), _layers(r),
                     CAMERA_ZH.get(r["features"].get("camera", "unknown"), "—"), desc[:40] + ("…" if len(desc) > 40 else ""), _route(r, units)])
    return ["", T("## 分镜表", "## Shot list")] + _table(
        ["#", T("时间", "Time"), T("时长", "Length"), T("底层画面", "Base picture"), T("素材来源", "Material"), T("叠加层", "Overlays"), T("运镜", "Camera"),
         T("画面", "Picture"), T("复刻", "Remake")], rows)


def _questions_md(b: dict) -> list[str]:
    qs = entities.open_questions(b)
    L = ["", T("## 不确定点", "## Open questions"), ""]
    L += [f"- {q}" for q in qs] or [T("- 没有需要特别复核的地方", "- Nothing needs a second look")]
    return L


def _shot_detail_md(r: dict) -> list[str]:
    base = r["base"]
    L = [f"![{r['id']}]({r['assets']['sheet']})", ""]
    probs = sorted(base["probs"].items(), key=lambda kv: -kv[1])[:3]
    L.append(T("- 概率：", "- Probabilities: ") + T("，", ", ").join(f"{LABEL_ZH[k]} {v:.0%}" for k, v in probs) + f"（{base['decided_by']}）")
    for key, name in (("uncertain", T("待确认", "To confirm")), ("disputed", T("有分歧", "Disputed"))):
        if base.get(key):
            L.append(f"- ⚠️ {name}{_colon()}{base[key]}")
    if base.get("scene_text"):
        L.append(T("- 画面里物体上的字（不是后期字幕）：", "- Text on objects in the scene (not subtitles): ") + join(base["scene_text"][:6]))
    if base.get("image_source"):
        L.append(T("- 静帧来源：{s}", "- Still source: {s}", s=base["image_source"]))
    L.append(T("- 素材来源：{o}", "- Material: {o}", o=_origin(r)))
    for it in (r.get("material") or {}).get("items", []):
        if it.get("real_material") and it.get("evidence"):
            L.append(f"  - {it['kind_zh']}{_colon()}{it['evidence']}")
    if base.get("generator_guess") and base["generator_guess"] != "unknown":
        L.append(T("- 可能的工具：{g}", "- Likely tool: {g}", g=base["generator_guess"]))
    if r.get("beats"):
        L.append(T("- 镜头内动效节拍：", "- Motion beats within the shot: ") + join(f"{t:.2f}s" for t in r["beats"]))
    L += [f"- {e}" for e in base["evidence"][:8]]
    v = r.get("vlm") or r.get("review") or {}
    if v.get("description"):
        L.append(T("- 画面：{d}", "- Picture: {d}", d=v["description"]))
    cl = aspects.shot_text(r) if base["label"] in aspects.PHOTOGRAPHIC else ""
    if cl:
        L.append(T("- 拍法/打光：{c}", "- Camera / lighting: {c}", c=cl))
    intrinsic = base["label"] in ("code_render", "screen_capture")
    for tr in r.get("text", {}).get("tracks", [])[:4]:
        kind = T("画面内容文字", "text in the picture") if intrinsic else KIND_ZH.get(tr["kind"], tr["kind"])
        L.append(T("- 文字轨（{k}/{b}）：", "- Text track ({k}/{b}): ", k=kind, b=tr["band"]) + " / ".join(t[:40] for t in tr["texts"][:4]))
    rep = r["replication"]
    L.append(T("- 复刻：{n}", "- Remake: {n}", n=rep["note"]))
    if rep.get("capsule", {}).get("image_prompt"):
        L.append(T("  - 首帧图像提示词：{p}", "  - First-frame image prompt: {p}", p=rep["capsule"]["image_prompt"]))
    if rep.get("capsule", {}).get("prompt"):
        L.append(T("  - 视频提示词：{p}", "  - Video prompt: {p}", p=rep["capsule"]["prompt"]))
    return L


def _appendix_md(b: dict) -> list[str]:
    L = ["", T("## 附录", "## Appendix"), "", T("### 逐镜取证", "### Shot by shot"), "",
         T("每个镜头的证据、概率、文字轨和提示词。默认折叠，点开看。", "Evidence, probabilities, text tracks and prompts per shot. Folded by default."), ""]
    for r in b["shots"]:
        title = f"#{r['index']} {fmt_time(r['start'])}–{fmt_time(r['end'])} · {r['verdict']}"
        L += [f"<details><summary>{html.escape(title)}</summary>", ""] + _shot_detail_md(r) + ["", "</details>", ""]
    prov = b.get("provenance", {})
    if prov.get("hints") or prov.get("encoder"):
        L += [T("### 元数据线索", "### Metadata clues"), ""]
        if prov.get("encoder"):
            L.append(T("- 编码器：`{e}`", "- Encoder: `{e}`", e=prov["encoder"]))
        for k, v in (prov.get("hints") or {}).items():
            L.append(f"- {k}{_colon()}{', '.join(v)}")
        L.append("")
    L += [T("### 说明", "### Notes"), "",
          T("- 确定性取证对「是否在动、是否整图推拉、是否渲染纹理、是否 24→30 帧率转换」很可靠；对实拍 / AI / 3D 的区分要依赖 VLM 与人工复核。",
            "- Deterministic forensics is reliable on motion, whole-frame pan/zoom, rendered texture and 24→30 fps conversion; telling live action from AI from 3D relies on the VLM and human review."),
          T("- 元数据经平台转码常被清除，缺失不代表没有。", "- Platform transcoding usually strips metadata; missing metadata proves nothing."),
          T("- 完整数据在 `breakdown.json`；agent 用 `rea-video summary` 读紧凑版。", "- The full data is in `breakdown.json`; agents read the compact view with `rea-video summary`."), ""]
    return L


def markdown(b: dict) -> str:
    L = _head_md(b) + _content_md(b) + _cast_md(b) + _audio_md(b) + _visual_md(b) + packaging_md(b) + _remake_md(b) + _shotlist_md(b) + _questions_md(b) + _appendix_md(b)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(L)).strip() + "\n"


# ------------------------------------------------------------------ HTML ------------------------------------------

_RE_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
# 只有报告自己生成的这几种行可以原样进 HTML；VLM / OCR 文字里换行带出来的标签一律转义
_RE_RAW_OK = re.compile(r"<details><summary>[^<>]*</summary>|</details>|<!--[^<>]*-->")


def _safe_url(m: re.Match, tpl: str) -> str:
    """Links / images only to http(s) or relative paths (no javascript:, data: ...)."""
    url = m.group(2)
    if ":" in url.split("/", 1)[0] and not url.lower().startswith(("http://", "https://")):
        return m.group(0)
    return tpl.format(text=m.group(1), url=url)
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_CODE = re.compile(r"`([^`]+)`")
_RE_SEP = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")


def _inline(s: str) -> str:
    s = html.escape(s, quote=True)
    s = _RE_CODE.sub(r"<code>\1</code>", s)
    s = _RE_BOLD.sub(r"<b>\1</b>", s)
    s = _RE_IMG.sub(lambda m: _safe_url(m, '<img src="{url}" alt="{text}" loading="lazy">'), s)
    s = _RE_LINK.sub(lambda m: _safe_url(m, '<a href="{url}">{text}</a>'), s)
    return s


def _md_to_html(lines: list[str], b: dict) -> str:
    """Just enough Markdown for our own reports: headings, lists (2 levels), tables, fences, images, bold, code, raw <details>."""
    out: list[str] = []
    lists: list[tuple[str, int]] = []  # (tag, indent)
    table: list[str] = []
    para: list[str] = []
    in_code = False
    in_section = False
    skip_table = False

    def close_lists(to_indent: int = -1):
        while lists and lists[-1][1] > to_indent:
            out.append(f"</{lists.pop()[0]}>")

    def flush():
        nonlocal table, para, skip_table
        close_lists()
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para = []
        if table:
            if not skip_table:
                head, *body = table
                out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c.strip())}</th>" for c in head.strip().strip("|").split("|")) + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{_inline(c.strip())}</td>" for c in row.strip().strip("|").split("|")) + "</tr>" for row in body) + "</tbody></table>")
            table = []
            skip_table = False

    for raw in lines:
        line = raw.rstrip()
        if in_code:
            if line.startswith("```"):
                in_code = False
                out.append("</pre>")
            else:
                out.append(html.escape(line))
            continue
        if line.startswith("```"):
            flush()
            in_code = True
            out.append("<pre class='prompt'>")
            continue
        if line == _MIX_MARK:
            flush()
            out.append(_mix_bar(b))
            skip_table = True
            continue
        if line == _STEMS_MARK:
            flush()
            out.append(_stems_html(b))
            continue
        if _RE_RAW_OK.fullmatch(line):  # our own details / summary / comments pass through
            flush()
            out.append(line)
            continue
        if not line.strip():
            flush()
            continue
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            text = _inline(line[level:].strip())
            if level == 2:
                if in_section:
                    out.append("</section>")
                out.append(f"<section class='card'><h2>{text}</h2>")
                in_section = True
            else:
                out.append(f"<h{level}>{text}</h{level}>")
            continue
        if line.lstrip().startswith("|"):
            if _RE_SEP.match(line.strip()):
                continue
            if para:
                flush()
            table.append(line)
            continue
        m = re.match(r"^(\s*)(?:[-*]|\d+\.)\s+(.*)$", line)
        if m:
            if table or para:
                flush()
            indent = len(m.group(1))
            tag = "ol" if re.match(r"^\s*\d+\.", line) else "ul"
            if lists and lists[-1][1] == indent:
                pass
            elif not lists or indent > lists[-1][1]:
                lists.append((tag, indent))
                out.append(f"<{tag}>")
            else:
                close_lists(indent)
                if not lists or lists[-1][1] != indent:
                    lists.append((tag, indent))
                    out.append(f"<{tag}>")
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue
        if table:
            flush()
        if _RE_IMG.fullmatch(line.strip()):
            flush()
            out.append(_inline(line.strip()).replace("<img ", "<img class='sb' "))
            continue
        close_lists()
        para.append(_inline(line.strip()))
    flush()
    if in_section:
        out.append("</section>")
    return "\n".join(out)


def _mix_bar(b: dict) -> str:
    esc = html.escape
    return "<div class='mix'>" + "".join(
        f"<div class='bar' style='flex:{m['ratio']};background:rgb({','.join(str(c) for c in LABEL_COLOR.get(m['label'], (80, 80, 80)))})' title='{esc(m['label_zh'])}'>{esc(m['label_zh'])} {m['ratio']:.0%}</div>"
        for m in b["summary"]["production_mix"]) + "</div>"


def _stems_html(b: dict) -> str:
    if not (b.get("stems") or {}).get("ok"):
        return ""
    return "<div class='stems'>" + "".join(
        f"<div>{name}{_colon()}<audio controls preload='none' src='stems/{f}'></audio></div>"
        for f, name in (("original.wav", T("原声", "original")), ("vocals.wav", T("人声干声", "dry voice")), ("music.wav", T("配乐 + 环境声", "music + ambience")))) + "</div>"


_CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--card:#fff;--line:#e7e5e4;--accent:#0d9488}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--card:#292524;--line:#44403c}}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:1100px;margin:auto} h1{font-size:22px} h2{font-size:18px;margin:4px 0 10px} h3{font-size:15px;margin:16px 0 6px} h4{font-size:13px;color:var(--muted);margin:10px 0 2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}
.mix{display:flex;height:30px;border-radius:6px;overflow:hidden;margin:12px 0} .bar{color:#fff;font-size:12px;padding:6px;white-space:nowrap;overflow:hidden}
img{max-width:100%;border-radius:6px} img.sb{display:block;margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0;display:block;overflow-x:auto} th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top} th{color:var(--muted);font-weight:600}
td img{max-height:70px}
ul,ol{margin:4px 0;padding-left:20px} li{margin:2px 0} p{margin:6px 0}
pre.prompt{background:var(--bg);padding:10px;border-radius:6px;font-size:13px;white-space:pre-wrap;word-break:break-word}
code{background:var(--bg);padding:1px 4px;border-radius:4px;font-size:13px}
details{margin:8px 0;border:1px solid var(--line);border-radius:8px;padding:6px 12px} summary{cursor:pointer;color:var(--accent);font-weight:600}
.stems div{margin:4px 0} audio{vertical-align:middle;max-width:100%}
"""


def html_report(b: dict) -> str:
    body = _md_to_html(markdown(b).split("\n"), b)
    return (f"<!doctype html><html lang=\"{lang()}\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{T('拆解：', 'Breakdown: ')}{html.escape(b['source']['filename'])}</title><style>{_CSS}</style></head><body><main>\n{body}\n</main></body></html>")


def write_reports(b: dict, out: Path) -> None:
    from .i18n import set_lang

    set_lang(b.get("lang", "zh"))
    (out / "report.md").write_text(markdown(b), encoding="utf-8")
    (out / "report.html").write_text(html_report(b), encoding="utf-8")
