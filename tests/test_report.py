"""Report structure: reading order, cast / script / music cards, folded detail, and the HTML rendered from the Markdown."""
import json
import re

import pytest

from rea_video.entities import cast, clean_cast, open_questions, script
from rea_video.i18n import set_lang
from rea_video.pipeline import decompose, finalize
from rea_video.report import html_report, markdown
from rea_video.review import apply_answers, build_tasks

CAST = {"style": "扁平 UI，深色底",
        "characters": [{"id": "A", "name": "小黄", "kind": "cartoon", "look": "黄色圆滚滚的小河马，粉色连体衣，斜挎粉包", "role": "主角", "voice": "", "shots": [1, 2, 3]},
                       {"id": "B", "name": "旁白", "kind": "person", "look": "", "role": "旁白", "voice": "青年男声", "shots": []},
                       {"name": "", "look": "", "kind": "bogus"}],
        "scenes": [{"id": "S1", "where": "城市街道", "when": "白天", "look": "虚化街景，暖日光", "shots": [1, 2]}],
        "props": [{"name": "粉色小挎包", "note": "角色一直背着", "shots": [1, 3]}, {"note": "no name"}]}


@pytest.fixture(scope="module")
def breakdown(media, tmp_path_factory):
    out = tmp_path_factory.mktemp("rep") / "edit"
    b = decompose(media["edit"], out, use_vlm=False, ocr=False, stems=False)
    return b, out


def _with_vlm(b: dict) -> dict:
    b = json.loads(json.dumps(b))
    b["whole_video_vlm"] = {
        "summary": "测试视频", "format": "知识讲解", "hook": "开头一张静帧", "overall_production": "代码渲染 + 静图",
        "segments": [{"start": 0, "end": 2, "beat": "铺垫", "copy": "你好", "audio": "音乐"}],
        "narration": {"type": "tts", "voice": "女声", "lines": [{"start": 0.0, "end": 1.0, "speaker": "A", "text": "你好"}, {"start": 1.0, "end": 2.0, "text": "再见"}]},
        "music": {"present": True, "style": "轻快", "genre": "pop", "mood": "开心", "instruments": ["钢琴"], "has_vocals": False,
                  "song_guess": "测试歌", "source_guess": "stock_library", "ending": "fade_out"},
        "sfx": [], "ambience": "无", "mix": "人声在上", "subtitles": {"present": False}, **CAST}
    # the synthetic clip is silent; give it a measured audio layer so the voice / music cards render
    b["audio"] = {"has_audio": True, "rms_dbfs": -20.0, "peak_dbfs": -3.0, "voice": {"present": True, "ratio": 0.4, "f0_median_hz": 210.0, "gender_hint": "female"},
                  "music": {"present": True, "ratio": 0.9, "start": 0.0, "end": 7.5, "tempo_bpm": 120.0, "tempo_alternatives": [60.0], "key": {"tonic": "C", "mode": "major", "confidence": 0.8},
                            "section_changes": [4.0]}, "cuts_on_beat_ratio": 0.5, "cuts_on_beat_chance": 0.3, "beat_synced_edit": True}
    b["audio_plan"] = {"sfx_merged": [{"t": 1.0, "type": "pop", "description": "弹出音", "source": "vlm", "on": {"what": "文字弹出"}}], "plan": [], "mix": ""}
    return b


def test_clean_cast_validates():
    c = clean_cast(CAST)
    assert [x["id"] for x in c["characters"]] == ["A", "B"]  # the entry without name / look is dropped
    assert c["characters"][0]["shots"] == [1, 2, 3] and c["scenes"][0]["where"] == "城市街道"
    assert [p["name"] for p in c["props"]] == ["粉色小挎包"]
    assert clean_cast(None) == {} and clean_cast({"characters": [{}]}) == {}


def test_cast_prefers_review_and_falls_back(breakdown):
    b, _ = breakdown
    set_lang("zh")
    c = cast(b)
    assert c["source"] is None and c["characters"] == []
    v = _with_vlm(b)
    assert cast(v)["source"] == "vlm" and cast(v)["style"] == "扁平 UI，深色底"
    v["review_cast"] = {"characters": [{"id": "X", "name": "复核角色", "kind": "person", "look": "看图填的", "shots": [2]}], "scenes": [], "props": [], "style": ""}
    c = cast(v)
    assert c["source"] == "review" and c["characters"][0]["name"] == "复核角色"
    assert c["props"][0]["name"] == "粉色小挎包"  # review left props empty → VLM props stay
    rows = script(v)
    assert [r["speaker"] for r in rows] == ["A", ""] and rows[1]["text"] == "再见"


def test_markdown_reading_order_and_cards(breakdown):
    b, _ = breakdown
    set_lang("zh")
    md = markdown(_with_vlm(b))
    heads = [l for l in md.splitlines() if l.startswith("## ")]
    want = ["## 内容与结构", "## 角色、场景与道具", "## 声音", "## 复刻方案", "## 分镜表", "## 不确定点", "## 附录"]
    idx = [heads.index(h) for h in want]
    assert idx == sorted(idx), heads
    assert md.index("## 内容与结构") < md.index("## 复刻方案") < md.index("### 逐镜取证")
    # cast table, scene table, props
    assert re.search(r"\| A \| 小黄 \| 卡通形象 \| 黄色圆滚滚的小河马.*\| #1、#2、#3 \|", md)
    assert "| S1 | 城市街道 | 白天 |" in md and "- 粉色小挎包（镜头 #1、#3）：角色一直背着" in md
    # script and music card
    assert "**脚本**（TTS 合成，女声）" in md and "| 0.0–1.0s | A | 你好 |" in md and "| 1.0–2.0s | 旁白 | 再见 |" in md
    assert "- 歌曲：测试歌" in md and "- 风格：轻快；pop；开心；钢琴；纯音乐" in md
    # per-shot forensics folded, one per shot; no internal rule ids in prose
    assert md.count("<details><summary>#") == len(b["shots"])
    assert not re.search(r"\bR\d\d-[a-z]|\bS0\d\b|A0\d\)", md), "rule ids leaked into the report"
    assert "capsule_cinema" not in md and "code_render_spec" not in md


def test_markdown_without_vlm_still_complete(breakdown):
    b, _ = breakdown
    set_lang("zh")
    md = markdown(b)
    assert "没有整片的内容概括" in md and "没有归纳出角色" in md and "## 不确定点" in md
    set_lang("en")
    try:
        md_en = markdown(b)
        assert "## Cast, scenes and props" in md_en and "## Open questions" in md_en and "<details><summary>#1 " in md_en
    finally:
        set_lang("zh")


def test_html_is_rendered_from_markdown(breakdown):
    b, _ = breakdown
    set_lang("zh")
    h = html_report(_with_vlm(b))
    for tag in ("ul", "ol", "table", "section", "details", "pre"):
        assert h.count(f"<{tag}") == h.count(f"</{tag}>"), tag
    assert "<div class='mix'>" in h and h.count("<h2>") >= 7
    assert "<td>小黄</td>" in h and "<img" in h
    # no raw Markdown left behind
    body = h.split("<main>")[1]
    assert not re.search(r"^(\| |- |\*\*|#{1,3} )", body, re.M), "unrendered markdown in HTML"
    assert "<!--mix-->" not in h and "<!--stems-->" not in h


def test_review_cast_flows_into_report(breakdown):
    b, out = breakdown
    set_lang("zh")
    b = json.loads(json.dumps(b))
    _, answers = build_tasks(b, out)
    assert "cast" in answers and answers["cast"]["characters"][0]["id"] == "A"
    answers["cast"] = CAST
    apply_answers(b, answers, by="tester")
    assert b["review_cast"]["by"] == "tester" and len(b["review_cast"]["characters"]) == 2
    b = finalize(b, out)
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "| A | 小黄 |" in md


def test_open_questions_collects_everything(breakdown):
    b, _ = breakdown
    set_lang("zh")
    b = json.loads(json.dumps(b))
    b["shots"][0]["base"]["disputed"] = "工具判 A、VLM 判 B"
    b["shots"][1]["base"]["confidence"] = 0.4
    b["sound_sources"] = {"music": {"source": "unknown", "source_zh": "来源待确认", "probs": {"a": 0.5, "b": 0.5}, "how_to_confirm": ["听歌识曲"]}}
    qs = open_questions(b)
    assert any("工具判 A" in q for q in qs) and any("#2" in q and "40%" in q for q in qs) and any("听歌识曲" in q for q in qs)
