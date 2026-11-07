"""Jump-cut pieces of one take share one VLM call; the call budget goes where the pixels are least sure."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from rea_video.overlay import shot_ocr_frames, shot_ocr_items
from rea_video.pipeline import decompose, vlm_units
from rea_video.vlm import take_results
from tests.conftest import _photo_like, _write
from tests.test_shots import H, W, _speaker


def _rec(i, start, end, trans="cut", sure=0.9):
    return {"index": i, "id": f"shot_{i:03d}", "start": start, "end": end, "duration": end - start, "transition_in": trans,
            "deterministic": {"probs": {"live_action": sure, "ai_video": 1 - sure}}}


def test_jump_pieces_form_one_unit_up_to_the_clip_limit():
    recs = [_rec(1, 0, 2, "start"), _rec(2, 2, 4, "jump"), _rec(3, 4, 6, "jump"), _rec(4, 6, 8, "cut"),
            _rec(5, 8, 15, "jump"), _rec(6, 15, 21, "jump")]
    units = vlm_units(recs, 60)
    assert [[r["index"] for r in u] for u in units] == [[1, 2, 3], [4, 5], [6]]  # 4+5 is 9 s; adding 6 would be 15 s


def test_call_budget_goes_to_uncertain_long_units_in_time_order():
    recs = [_rec(1, 0, 1, "start", 0.95), _rec(2, 1, 5, "cut", 0.5), _rec(3, 5, 6, "cut", 0.55), _rec(4, 6, 9, "cut", 0.9)]
    assert [u[0]["index"] for u in vlm_units(recs, 2)] == [2, 3]


def test_take_answer_is_split_per_piece():
    raw = {"label_probs": {"live_action": 1}, "description": "整段", "replication": {"image_prompt": "首帧", "video_prompt": "整段动作"},
           "segments": [{"description": "拆开盒子", "replication": {"video_prompt": "双手拆开纸盒"}},
                        {"description": "拿出杯子", "replication": {"video_prompt": "从盒里拿出水杯"}}]}
    a, b = take_results(raw, 2)
    assert a["description"] == "拆开盒子" and b["replication"]["video_prompt"] == "从盒里拿出水杯"
    assert a["replication"]["image_prompt"] == "首帧" and "segments" not in a  # shared fields stay, pieces do not leak
    c, d = take_results({"description": "整段", "segments": [{"description": "只有一段"}]}, 2)  # wrong count: shared answer
    assert c["description"] == d["description"] == "整段"


def test_shot_text_comes_from_the_whole_video_ocr_pass():
    whole = [{"t": 1.0, "text": "字幕", "conf": 0.9, "bbox": [0.2, 0.8, 0.6, 0.05], "angle": 0.0},
             {"t": 2.0, "text": "下一句", "conf": 0.9, "bbox": [0.2, 0.8, 0.6, 0.05], "angle": 0.0}]
    hits = shot_ocr_items(whole, 0.5, 0.8, 1.6)
    assert [h["text"] for h in hits] == ["字幕"] and hits[0]["band"] == "bottom"
    assert shot_ocr_items(whole, 0.5, 1.6, 1.9) is None  # no read inside this shot: read its own frames
    assert shot_ocr_items(whole, 2.5, 0, 3) is None  # too sparse (long video): read its own frames
    assert [shot_ocr_frames(d) for d in (0.3, 1.2, 6.0)] == [1, 2, 4]


TAKE = {"label_probs": {"live_action": 0.9, "ai_video": 0.1}, "image_source": "photo", "evidence": ["手持轻微抖动"],
        "description": "整条口播", "shot_size": "近景", "camera_move": "固定", "style": "实拍",
        "replication": {"image_prompt": "人物近景", "video_prompt": "人物对镜头说话"}}


class Handler(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = body["messages"][0]["content"][-1]["text"]
        Handler.seen.append(text)
        if "label_probs" in text:
            n = text.count("segments 数组") and int(text.split("剪成的 ")[1].split(" 段")[0])
            payload = dict(TAKE, segments=[{"description": f"第{k + 1}段", "replication": {"video_prompt": f"第{k + 1}段动作"}}
                                           for k in range(n)]) if n else TAKE
        else:
            payload = {"summary": "测试", "segments": []}
        data = json.dumps({"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def fake_server(monkeypatch):
    Handler.seen = []
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("REA_VLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("REA_VLM_API_KEY", "test")
    monkeypatch.setenv("REA_VLM_MODEL", "fake-model")
    yield Handler
    srv.shutdown()


def test_jump_cut_take_is_one_vlm_call(tmp_path, fake_server):
    rng = np.random.default_rng(2)
    bg = _photo_like(W, H, 5)
    frames = [_speaker(bg, 180, 160, t, rng) for t in range(45)]
    frames += [_speaker(bg, 120, 210, t, rng) for t in range(45, 90)]
    frames += [_speaker(bg, 200, 150, t, rng) for t in range(90, 135)]
    p = _write(frames, tmp_path / "take.mp4")
    b = decompose(p, tmp_path / "o", use_vlm=True, whole_vlm=False, ocr=False, workers=1, stems=False, packaging=False, memory=False)
    shots = b["shots"]
    assert [s["transition_in"] for s in shots] == ["start", "jump", "jump"]
    assert sum("label_probs" in t for t in fake_server.seen) == 1  # one look at the whole take
    assert [s["vlm"]["description"] for s in shots] == ["第1段", "第2段", "第3段"]
    assert all(s["vlm"]["take"]["shots"] == [1, 2, 3] for s in shots)
    assert b["analysis"]["vlm"]["calls"] == 1 and b["analysis"]["vlm"]["ok_shots"] == 3
