"""Agent-as-VLM: a multimodal agent looks at the shot images and answers the same questions
the VLM would. `build_tasks` writes what to look at; `apply_answers` folds the answers back
into the breakdown so the summary, reports and replication plan reflect what the agent saw.
"""
from __future__ import annotations

import re
import shlex
import time

from .classify import LABEL_ZH, LABELS, top
from . import aspects
from .vlm import SHOT_PROMPT, shot_hints

AGENT_WEIGHT = 0.85  # agent answers are softened toward uniform before fusion
IMAGE_SOURCES = ("ai_image", "photo", "graphic", "screenshot", "unknown")
EDIT_KINDS = ("face_swap", "lip_sync", "restyle", "outfit_swap", "bg_replace", "object_edit", "beautify")
ASSET_KINDS = ("real_footage", "photo", "screenshot", "screen_recording", "product_photo", "logo", "ai_image")

# category definitions, taken from the VLM prompt so both paths ask the same question
LABEL_GUIDE = re.search(r"底层画面类别.*?\n\n", SHOT_PROMPT, re.S).group(0).strip()
CONFUSIONS = re.search(r"注意区分：.*?\n\n", SHOT_PROMPT, re.S).group(0).strip()
ASPECT_GUIDE = aspects.review_guide()

INSTRUCTIONS = f"""你是这次的 VLM：逐个镜头看图，判断「底层画面」的制作方式，把答案写进 review_answers.json，然后运行
  rea-video apply-review <输出目录> --by <你的名字>
把你的判断并入结论（会重写 breakdown.json、report.md、report.html）。

怎么看：
1. 先看 storyboard.jpg 建立整体印象；每个镜头看 images 里的 sheet（首/中/尾联系表），需要时运行 zoom_cmd 抽帧细看。
2. priority=high 的镜头（低置信、次选接近、转码后实拍/AI 待确认）一定要看；其余镜头也尽量都答。
3. 只依据画面证据，独立判断（这里不给 VLM 的答案，它会在融合时单独计入）。tool 一栏是确定性取证的结果，可能有误，但帧率类证据（24→30 重复帧）和 AIGC 标识可靠，
   和画面印象冲突时不要轻易推翻（见 SKILL.md「平台转码视频」）。
4. 看不出就把概率分散开，例如 ai_video 0.55 / live_action 0.45，并在 evidence 写清缺什么证据。
5. 没看过的镜头不要填（保持 label_probs 全 0），apply-review 会跳过它。

{LABEL_GUIDE}

{CONFUSIONS}

每个镜头要填：label_probs（{len(LABELS)} 类，和为 1）、image_source（{"|".join(IMAGE_SOURCES)}）、evidence（看到的具体证据）、
description（主体、动作、场景、运镜；代码渲染画面写清图形元素是什么（粒子/渐变/图表/卡片/文字/矢量图形）、拼成什么形状、颜色、怎么动、文字和数字组件在哪，报告的「代码合成」逐镜表直接用它；代码镜头另有 images.strip 关键帧条（约每 0.5 秒一张），报告「逐镜动效时间轴」已测好每个元素的位置、出现时间、方向、快慢和色值，你按编号补「它是什么」即可，例如"1–12：圆角图标卡片，依次弹入"）、embedded_assets（画面里的真实素材：截图、照片、实拍片段、Logo，
kind 取 {"|".join(ASSET_KINDS)}，is_real_material 为 true/false）。
某个镜头其实是多刀合并的（暗底图形卡和暗底口播交替时，切点分数低容易被合成一个长镜头）就加 split_suggestion：
{{"cuts": [切点秒数], "labels": [各段类别，比 cuts 多一个], "note": "看到的交替结构"}}，报告会在该镜头标注拆分建议；不是合并段就不要填。
实拍或定格镜头被 AI 二次加工过时填 ai_edits：[{{"kind": "{"|".join(EDIT_KINDS)}", "evidence": "看到的破绽"}}]（换脸、对口型、风格化、换装、换背景、加删物体、美颜）；没有就留空。
AI 生成 / 3D / 实拍镜头再填 replication：image_prompt（复刻首帧的中文图像提示词：主体、构图、光线、风格，具体可执行）、
video_prompt（复刻该镜头的中文视频提示词：写清动作过程和结束状态、运镜；只写想要的内容，不写否定句）、video_prompt_en（英文版）。
这些提示词会被合并进「生成单元」的多镜头提示词，所以每镜只写这一镜的内容，统一的风格和场景描述写在 description 里即可。

实拍/写实镜头再填 aspects（怎么拍、怎么打光；纯图形/界面画面不填），像素测不出的部分靠你看：
{ASPECT_GUIDE}
工具已经测了景别、主体光比、主光左右/上下、软硬、色温、背景虚化（见每镜 aspects），你主要补：机位角度、
拍摄方式（自拍/支架）、主光是什么光源、眼神光、轮廓光/背景灯、画面里可见的光源；和测量冲突时写明依据。
最后在答案顶层的 aspects 里写整片：机位/场景、推测设备、整体布光、剪辑手法、视频形式。

答案顶层的 cast 写整片的角色、场景和道具（看 storyboard.jpg 和各镜截图）：characters 每个主要角色一条（id 编号、name 称呼、kind person|animal|cartoon|avatar|product|other、
look 外观写到能据此再画出同一个角色、role 作用、voice 音色、shots 出场镜头号）；同一个角色在不同镜头要认成同一个。scenes 每个地点一条（id、where、when、look、shots）；
props 道具 / 商品 / Logo（name、note、shots）；style 一句整体视觉风格与调色。

剪辑包装（tasks.packaging，有才做）：
- stickers：工具找到的贴纸 / 动图 / 画中画，看 image（贴纸截图）和 frame_cmd 抽的帧，在答案 packaging.stickers 里填
  is_overlay（true = 后期贴上去的；false = 画面本身的东西，例如 3D 里突然出现的物体）和 what（表情包 / GIF / emoji / 箭头 / 小窗里放的什么）。
- text：工具分好类的花字 / 标题 / 文字标注，分错了就在 packaging.text 里填 kind（subtitle / huazi / title / label / counter / scene；counter 是跳动的数字）。
- 工具漏掉的贴纸、动图，写进 packaging.missed：{{"t0": 秒, "t1": 秒, "what": "...", "where": "画面位置"}}。"""



def _tiles_cmd(video, t0: float, t1: float, every: float, out: str) -> str:
    """Shell-ready `rea-video tiles` command (paths quoted: file names often have spaces)."""
    return (f"rea-video tiles {shlex.quote(str(video))} --start {t0:.2f} --end {t1:.2f} --every {every:g} "
            f"-o {shlex.quote(out)}")

def _priority(rec: dict, ctx: dict) -> tuple[str, list[str]]:
    det = (rec.get("deterministic") or {}).get("probs") or {}
    probs = sorted(det.items(), key=lambda kv: -kv[1])
    label, conf = probs[0] if probs else ("", 1.0)
    why = []
    if conf < 0.65:
        why.append(f"置信度低（{conf:.0%}）")
    if len(probs) > 1 and probs[0][1] - probs[1][1] < 0.25:
        why.append(f"次选 {LABEL_ZH.get(probs[1][0], probs[1][0])} 接近（{probs[1][1]:.0%}）")
    if (rec.get("base") or {}).get("disputed"):
        why.append(rec["base"]["disputed"])
    facts = (rec.get("deterministic") or {}).get("facts", {})
    if label == "ai_video" and facts.get("pulldown") in ("24→30", "24→60", "25→30?"):
        why.append("只有 24fps 源的帧率证据：AI 和 24p 相机实拍都会这样，看画面定")
    if facts.get("transcode_degraded") and label in ("ai_video", "live_action"):
        why.append("平台转码，实拍/AI 待确认")
    return ("high" if why else "normal"), why


def build_tasks(breakdown: dict, out_dir: str) -> tuple[dict, dict]:
    """-> (tasks, empty answer template)."""
    video = breakdown["source"]["path"]
    ctx = breakdown.get("video_context") or {}
    from .memory import hint_for, patterns

    pats = patterns()
    shots = []
    for rec in breakdown["shots"]:
        # only the deterministic layer is shown: the agent should judge independently of any VLM answer
        ranked = sorted(rec["deterministic"]["probs"].items(), key=lambda kv: -kv[1])
        alt = ranked[1:2]
        prio, why = _priority(rec, ctx)
        dl, dp = top(rec["deterministic"]["probs"])
        past = hint_for(dl, pats)
        if past:
            prio, why = "high", why + [past]
        shots.append({
            "id": rec["id"], "index": rec["index"], "start": rec["start"], "end": rec["end"], "duration": rec["duration"],
            "priority": prio, "why": why,
            "tool": {"label": dl, "label_zh": LABEL_ZH[dl], "confidence": round(dp, 3),
                     "second": [alt[0][0], round(alt[0][1], 3)] if alt else None,
                     "evidence": rec["deterministic"]["evidence"][:6]},
            "hints": shot_hints(rec["features"], rec["deterministic"]["facts"], dl, dp),
            "aspects": {k: v["result"] for k, v in (rec.get("aspects") or {}).items() if v.get("result")},
            "images": {"sheet": rec["assets"]["sheet"], "first": rec["assets"]["first_frame"], "last": rec["assets"]["last_frame"],
                       **({"strip": rec["assets"]["strip"]} if rec["assets"].get("strip") else {})},
            "zoom_cmd": _tiles_cmd(video, rec["start"], rec["end"], 0.2, f"{out_dir}/check_{rec['id']}.jpg"),
        })
    pack = breakdown.get("packaging") or {}
    pk_tasks, pk_answers = None, None
    if pack:
        sts = [st for st in pack.get("stickers", []) if st.get("bbox")]
        txt = [c for c in pack.get("text_cues", []) if c["kind"] not in ("subtitle",)]
        pk_tasks = {"stickers": [{"id": st["id"], "t0": st["t0"], "t1": st["t1"], "kind_zh": st["kind_zh"], "confidence": st.get("confidence"),
                                  "in_picture": bool(st.get("in_picture")), "image": st.get("image"), "bbox": st["bbox"],
                                  "frame_cmd": _tiles_cmd(video, st["t0"], st["t1"], 0.25, f"{out_dir}/check_{st['id']}.jpg")}
                                 for st in sts],
                    "text": [{"id": c["id"], "t0": c["t0"], "t1": c["t1"], "text": c["text"], "kind": c["kind"], "style": c.get("style_zh", "")}
                             for c in txt[:80]]}
        pk_answers = {"stickers": [{"id": st["id"], "is_overlay": None, "what": ""} for st in sts],
                      "text": [{"id": c["id"], "kind": ""} for c in txt[:80]], "missed": []}
    tasks = {"instructions": INSTRUCTIONS, "video": video, "storyboard": "storyboard.jpg",
             "video_context": {k: ctx.get(k) for k in ("transcoded", "platform", "native30") if k in ctx},
             "aigc": (breakdown.get("provenance") or {}).get("aigc"),
             "shots": shots}
    if pk_tasks:
        tasks["packaging"] = pk_tasks
    answers = {"by": "", "shots": [{"id": s["id"], "time": f"{s['start']:.2f}-{s['end']:.2f}",
                                     "label_probs": {k: 0 for k in LABELS}, "image_source": "unknown",
                                     "evidence": [], "description": "", "embedded_assets": [], "ai_edits": [],
                                     "replication": {"image_prompt": "", "video_prompt": "", "video_prompt_en": ""},
                                     "aspects": aspects.review_template()} for s in shots],
               "aspects": aspects.review_template(video=True),
               "cast": {"style": "", "characters": [{"id": "A", "name": "", "kind": "", "look": "", "role": "", "voice": "", "shots": []}],
                        "scenes": [{"id": "S1", "where": "", "when": "", "look": "", "shots": []}], "props": [{"name": "", "note": "", "shots": []}]}}
    if pk_answers:
        answers["packaging"] = pk_answers
    return tasks, answers


def _clean_split(sp) -> tuple[dict | None, str | None]:
    """Optional reviewer note that a shot is really several cuts: {cuts: [秒], labels: [类别], note}. Malformed
    input is reported, not raised: the answers file is written by an agent and one bad field must not stop apply-review."""
    if not isinstance(sp, dict) or not sp.get("cuts"):
        return None, None
    cuts_in, labels_in = sp.get("cuts"), sp.get("labels") or []
    if not isinstance(cuts_in, list) or not isinstance(labels_in, list):
        return None, "split_suggestion 的 cuts / labels 要是列表"
    try:
        cuts = [float(c) for c in cuts_in]
    except (TypeError, ValueError):
        return None, "split_suggestion.cuts 里有不是数字的秒点"
    bad = [x for x in labels_in if x not in LABELS]
    if bad:
        return None, f"split_suggestion.labels 有未知类别 {bad}（可选：{', '.join(LABELS)}）"
    return {"cuts": sorted(cuts)[:12], "labels": list(labels_in)[:12], "note": str(sp.get("note", ""))[:300]}, None


def _clean(ans: dict) -> tuple[dict | None, str | None]:
    probs = ans.get("label_probs") or {}
    bad = [k for k in probs if k not in LABELS]
    if bad:
        return None, f"未知类别 {bad}（可选：{', '.join(LABELS)}）"
    vals = {}
    for k in LABELS:
        try:
            vals[k] = max(0.0, float(probs.get(k, 0) or 0))
        except (TypeError, ValueError):
            return None, f"{k} 的概率不是数字"
    total = sum(vals.values())
    if total <= 0:
        return None, "label_probs 全为 0（没作答），跳过"
    u = 1.0 / len(LABELS)
    soft = {k: AGENT_WEIGHT * v / total + (1 - AGENT_WEIGHT) * u for k, v in vals.items()}
    src = ans.get("image_source") if ans.get("image_source") in IMAGE_SOURCES else "unknown"
    rep_in = ans.get("replication") if isinstance(ans.get("replication"), dict) else {}
    rep = {k: str(rep_in.get(k) or "").strip() for k in ("image_prompt", "video_prompt", "video_prompt_en") if str(rep_in.get(k) or "").strip()}
    assets = []
    for e in ans.get("embedded_assets") or []:
        if isinstance(e, dict) and e.get("kind") in ASSET_KINDS:
            assets.append({"kind": e["kind"], "description": str(e.get("description", "")),
                           "is_real_material": bool(e.get("is_real_material", e["kind"] != "ai_image"))})
    split, err = _clean_split(ans.get("split_suggestion"))
    if err:
        return None, err
    return {"label_probs": soft, "raw_probs": {k: round(v / total, 3) for k, v in vals.items()}, "image_source": src,
            "evidence": [str(x) for x in (ans.get("evidence") or [])][:8], "description": str(ans.get("description", "")),
            "embedded_assets": assets, "replication": rep, "aspects": aspects.clean_answers(ans.get("aspects")),
            "split_suggestion": split,
            "ai_edits": [{"kind": e["kind"], "evidence": str(e.get("evidence", ""))} for e in (ans.get("ai_edits") or [])
                         if isinstance(e, dict) and e.get("kind") in EDIT_KINDS]}, None


def apply_answers(breakdown: dict, answers: dict, by: str | None = None) -> dict:
    """Store answers on the shots (rec["review"]) and return a change log. Call finalize() afterwards."""
    by = by or answers.get("by") or "agent"
    recs = {r["id"]: r for r in breakdown["shots"]}
    applied, problems, changes = [], [], []
    for ans in answers.get("shots") or []:
        sid = ans.get("id")
        if sid not in recs:
            problems.append(f"{sid}: 没有这个镜头")
            continue
        clean, err = _clean(ans)
        if err:
            problems.append(f"{sid}: {err}")
            continue
        clean["_by"] = by
        rec = recs[sid]
        before = rec["base"]["label"]
        rec["review"] = clean
        applied.append(sid)
        changes.append((sid, before))
    pk = answers.get("packaging")
    if isinstance(pk, dict) and breakdown.get("packaging"):
        kinds = ("subtitle", "huazi", "title", "label", "counter", "scene")
        clean_pk = {"stickers": {str(a["id"]): {"is_overlay": bool(a["is_overlay"]), "what": str(a.get("what", ""))[:80]}
                                 for a in pk.get("stickers") or [] if isinstance(a, dict) and isinstance(a.get("is_overlay"), bool)},
                    "text": {str(a["id"]): a["kind"] for a in pk.get("text") or [] if isinstance(a, dict) and a.get("kind") in kinds},
                    "missed": [m for m in pk.get("missed") or [] if isinstance(m, dict) and "t0" in m], "by": by}
        if clean_pk["stickers"] or clean_pk["text"] or clean_pk["missed"]:
            breakdown["packaging"]["review"] = clean_pk
    whole = aspects.clean_answers(answers.get("aspects"), video=True)
    if whole:
        breakdown["review_aspects"] = whole
    from .entities import clean_cast

    cast = clean_cast(answers.get("cast"))
    if cast:
        cast["by"] = by
        breakdown["review_cast"] = cast
    breakdown.setdefault("analysis", {})["review"] = {"by": by, "shots": len(applied), "of": len(breakdown["shots"]),
                                                       "time": time.strftime("%Y-%m-%d %H:%M"), "problems": problems}
    return {"applied": applied, "problems": problems, "before": dict(changes)}
