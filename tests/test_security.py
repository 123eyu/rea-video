"""Hardening: report HTML escaping, env loading, remake path handling."""
import json
import subprocess
import sys
from pathlib import Path

from rea_video.report import _inline, _md_to_html


def test_inline_blocks_attribute_injection_and_bad_schemes():
    assert "onerror=\"" not in _inline('![a](x"onerror="alert(1))')
    assert "<a" not in _inline("[x](javascript:alert(1))")
    assert "<a" not in _inline("[x](JavaScript:alert(1))")
    assert '<a href="https://a.com/b">ok</a>' in _inline("[ok](https://a.com/b)")
    assert '<img src="frames/shot_001.jpg"' in _inline("![s](frames/shot_001.jpg)")


def test_raw_html_lines_only_for_our_own_tags():
    b = {"summary": {"production_mix": []}}
    out = _md_to_html(["- VLM 说明", "<img src=x onerror=alert(1)>", "<details><summary>镜头</summary>", "</details>"], b)
    assert "<img src=x" not in out and "&lt;img src=x" in out
    assert "<details><summary>镜头</summary>" in out


def test_cwd_env_is_not_loaded(tmp_path, monkeypatch):
    from rea_video import cli

    (tmp_path / ".env").write_text("REA_TEST_FROM_CWD=1\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("REA_TEST_FROM_CWD", raising=False)
    monkeypatch.setattr("rea_video.memory.pref", lambda k: None)
    cli._env(type("A", (), {"env_file": None})())
    import os
    assert "REA_TEST_FROM_CWD" not in os.environ


RUN_REMAKE = Path(__file__).resolve().parent.parent / "rea_video/integrations/run_remake.py"


def _run_remake(jobs: Path, root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RUN_REMAKE), "--jobs", str(jobs), "--capsule-root", str(root), "--dry-run", *extra],
                          capture_output=True, text=True)


def test_run_remake_rejects_foreign_capsule_root_and_output_dir(tmp_path):
    root = tmp_path / "capsule"
    job = {"executor": "capsule_cinema", "shot": 1, "label": "ai_video",
           "params": {"prompt": "p", "output_dir": str(root / "output/x")}}
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"capsule_root": str(tmp_path / "evil"), "run_dir": "r", "jobs": [job]}))
    r = _run_remake(jobs, root)
    assert r.returncode != 0 and "capsule_root" in r.stderr
    job["params"]["output_dir"] = str(tmp_path / "elsewhere")
    jobs.write_text(json.dumps({"capsule_root": str(root), "run_dir": "r", "jobs": [job]}))
    r = _run_remake(jobs, root)
    assert r.returncode != 0 and "output_dir" in r.stderr
    job["params"]["output_dir"] = str(root / "output/x")
    jobs.write_text(json.dumps({"capsule_root": str(root), "run_dir": "r", "jobs": [job]}))
    assert _run_remake(jobs, root).returncode == 0


def test_face_model_checksum_rejects_tampered_download(tmp_path, monkeypatch):
    from rea_video import faces

    monkeypatch.setenv("REA_VIDEO_MODELS", str(tmp_path))
    monkeypatch.setattr(faces.urllib.request, "urlretrieve", lambda url, dst: open(dst, "wb").write(b"evil"))
    assert faces._ensure_model() is None
    assert list(tmp_path.iterdir()) == []


def test_run_remake_only_accepts_shot_ids(tmp_path):
    root = tmp_path / "capsule"
    jobs_list = [{"executor": "capsule_cinema", "shot": i, "label": "ai_video",
                  "params": {"prompt": f"p{i}", "output_dir": str(root / f"output/{i}")}} for i in (1, 3)]
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"capsule_root": str(root), "run_dir": "r", "jobs": jobs_list}))
    for only in ("3", "shot_003", "SHOT_3"):
        r = _run_remake(jobs, root, "--only", only)
        assert r.returncode == 0 and r.stdout.startswith("1 generation job") and '"p3"' in r.stdout, (only, r.stderr)
    for bad in ("abc", "7"):
        r = _run_remake(jobs, root, "--only", bad)
        assert r.returncode != 0 and "--only" in r.stderr
