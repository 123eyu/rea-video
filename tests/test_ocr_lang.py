import sys
import types

import pytest

from rea_video import overlay


@pytest.fixture
def fake_rapidocr(monkeypatch):
    calls = []

    class RapidOCR:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", types.SimpleNamespace(RapidOCR=RapidOCR))
    monkeypatch.setattr(overlay, "_OCR", {})
    return calls


def test_default_language_is_zh(monkeypatch):
    monkeypatch.delenv("REA_OCR_LANG", raising=False)
    assert overlay.ocr_lang() == "zh"


def test_unknown_language_is_rejected(monkeypatch):
    monkeypatch.setenv("REA_OCR_LANG", "fr")
    with pytest.raises(ValueError):
        overlay.ocr_lang()


def test_zh_uses_bundled_model(monkeypatch, fake_rapidocr):
    monkeypatch.setenv("REA_OCR_LANG", "zh")
    assert overlay.get_ocr() is overlay.get_ocr()
    assert fake_rapidocr == [{}]


def test_ja_uses_japanese_recognizer(monkeypatch, tmp_path, fake_rapidocr):
    model = tmp_path / "japan.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("REA_OCR_REC_MODEL", str(model))
    monkeypatch.setenv("REA_OCR_LANG", "ja")
    overlay.get_ocr()
    monkeypatch.setenv("REA_OCR_LANG", "zh")
    overlay.get_ocr()
    assert fake_rapidocr == [{"rec_model_path": str(model)}, {}]  # one instance per language


def test_cached_model_with_matching_checksum_is_not_downloaded(monkeypatch, tmp_path):
    monkeypatch.delenv("REA_OCR_REC_MODEL", raising=False)
    monkeypatch.setenv("REA_VIDEO_MODELS", str(tmp_path))
    name, _url, _sha = overlay._REC_MODELS["ja"]
    (tmp_path / name).write_bytes(b"model")
    monkeypatch.setitem(overlay._REC_MODELS, "ja", (name, "http://invalid", overlay._sha256(tmp_path / name)))
    monkeypatch.setattr(overlay.urllib.request, "urlretrieve", lambda *a: pytest.fail("should not download"))
    assert overlay.rec_model("ja") == tmp_path / name


def test_ocr_lang_pref_is_validated(monkeypatch, tmp_path):
    from rea_video import memory

    monkeypatch.setenv("REA_VIDEO_HOME", str(tmp_path))
    with pytest.raises(ValueError):
        memory.set_pref("ocr_lang", "fr")
