import json
import subprocess
import sys
from pathlib import Path

import pytest

from rea_video.classify import LABELS, deterministic, fuse, top
from rea_video.integrations.capsule_cinema import build_remake_jobs, export_capsule_analysis
from rea_video.media import video_info
from rea_video.pipeline import decompose, finalize
from rea_video.remake import assemble
from rea_video.shots import build_track, detect_shots

ROOT = Path(__file__).resolve().parents[1]


def test_capabilities_valid():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/validate_capabilities.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_shot_boundaries(media):
    info = video_info(media["edit"])
    shots = detect_shots(build_track(str(media["edit"]), info))
    starts = [round(s.start, 2) for s in shots[1:]]
    assert len(shots) == 3, starts
    assert abs(starts[0] - 2.0) < 0.07 and abs(starts[1] - 5.0) < 0.07


@pytest.fixture(scope="module")
def breakdown(media, tmp_path_factory):
    out = tmp_path_factory.mktemp("out") / "edit"
    return decompose(media["edit"], out, use_vlm=False, ocr=False, stems=False), out


def test_labels(breakdown):
    b, _ = breakdown
    labels = [s["base"]["label"] for s in b["shots"]]
    assert labels == ["static_hold", "still_motion", "code_render"], labels


def test_kenburns_measured(breakdown):
    b, _ = breakdown
    km = b["shots"][1]["features"]
    assert 0.025 < km["zoom_per_s"] < 0.06, km["zoom_per_s"]
    assert km["camera"] == "planar_zoom_pan"


def test_outputs_and_schema(breakdown):
    b, out = breakdown
    for name in ("breakdown.json", "report.md", "report.html", "storyboard.jpg"):
        assert (out / name).is_file(), name
    assert b["schema"] == "rea_video.breakdown.v1"
    assert abs(sum(m["ratio"] for m in b["summary"]["production_mix"]) - 1.0) < 0.01
    for s in b["shots"]:
        assert set(s["base"]["probs"]) == set(LABELS)
        assert s["replication"]["rule"].startswith("R")


def test_finalize_idempotent(breakdown):
    b, out = breakdown
    again = finalize(json.loads((out / "breakdown.json").read_text()), out)
    assert [s["base"]["label"] for s in again["shots"]] == [s["base"]["label"] for s in b["shots"]]


def test_fuse_respects_frozen():
    det = {k: 0.0 for k in LABELS} | {"static_hold": 0.9, "code_render": 0.1}
    vlm = {k: 0.0 for k in LABELS} | {"ai_video": 0.9, "static_hold": 0.1}
    lab, _ = top(fuse(det, vlm, "frozen"))
    assert lab == "static_hold"


def test_vlm_can_override_camera_like():
    f = {"noise_sigma": 0.5, "temporal_noise": 0.8, "flat_ratio": 0.05, "palette95": 200, "axis_edge_ratio": 0.2,
         "dup_ratio": 0.0, "zero_pixel_ratio": 0.5, "camera": "smooth_move", "kenburns_score": 0.0, "moving_pair_ratio": 0.9}
    det, _, facts = deterministic(f)
    vlm = {k: 0.0 for k in LABELS} | {"live_action": 0.95, "ai_video": 0.05}
    assert top(fuse(det, vlm, facts["temporal_family"]))[0] == "live_action"


def test_capsule_export(breakdown, tmp_path):
    b, _ = breakdown
    p = export_capsule_analysis(b, tmp_path / "capsule_analysis.json")
    data = json.loads(p.read_text())
    for key in ("summary", "source_profile", "segments", "capsule_recipe", "execution_strategy", "content_scope"):
        assert key in data
    cs = data["content_scope"]
    assert cs["schema_version"] == "capsule.content_scope.v1" and cs["series_fixed"] and cs["episode_variable"]
    assert data["execution_strategy"]["mode"] == "review_required"


def test_remake_jobs_and_assemble(breakdown, tmp_path):
    b, out = breakdown
    jobs_path = build_remake_jobs(b, out, capsule_root=tmp_path / "capsule", engine="seedance2.0")
    jobs = json.loads(jobs_path.read_text())["jobs"]
    execs = [j["executor"] for j in jobs]
    assert execs == ["local_ffmpeg", "local_ffmpeg", "keep_original"], execs
    results = jobs_path.with_name("results.json")
    results.write_text(json.dumps({"results": {}}))
    res = json.loads(assemble(out / "breakdown.json", results))
    assert Path(res["remake"]).is_file() and Path(res["compare"]).is_file()
    info = video_info(res["remake"])
    assert abs(info.duration - b["source"]["duration"]) < 0.2


def test_english_report_has_no_chinese(media, tmp_path):
    import re

    from rea_video.i18n import set_lang

    try:
        b = decompose(media["edit"], tmp_path / "en", use_vlm=False, ocr=False, stems=False, lang="en")
        assert b["lang"] == "en"
        assert b["shots"][0]["base"]["label_zh"] == "static hold"
        cjk = re.compile(r"[一-鿿]")
        for name in ("report.md", "report.html"):
            bad = [l for l in (tmp_path / "en" / name).read_text().splitlines() if cjk.search(l)]
            assert not bad, f"{name} still has Chinese lines:\n" + "\n".join(bad[:20])
        # the same breakdown rendered again in Chinese
        b["lang"] = "zh"
        again = finalize(b, tmp_path / "en")
        assert again["shots"][0]["base"]["label_zh"] == "静帧停留"
    finally:
        set_lang("zh")
