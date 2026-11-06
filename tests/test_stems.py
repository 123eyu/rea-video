import numpy as np

from rea_video import stems as S


def test_stft_roundtrip_matches_input():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal((2, S.CHUNK)) * 0.1).astype(np.float32)
    y = S._istft(S._stft(x))
    mid = slice(S.TRIM, -S.TRIM)
    err = np.abs(y[:, mid] - x[:, mid]).std() / x.std()
    assert y.shape == x.shape and err < 0.02  # only the top bins above DIM_F are dropped


def test_extract_stems_without_audio(tmp_path):
    assert S.extract_stems(tmp_path / "missing.mp4", tmp_path)["ok"] is False


def test_ensure_model_rejects_partial_download_and_leaves_no_temp(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setenv("REA_VIDEO_MODELS", str(tmp_path))
    monkeypatch.setattr(S.urllib.request, "urlretrieve", lambda url, dst: open(dst, "wb").write(b"x" * 10))
    with pytest.raises(OSError):
        S.ensure_model()
    assert list(tmp_path.iterdir()) == []


def test_ensure_model_uses_unique_temp_names(tmp_path, monkeypatch):
    monkeypatch.setenv("REA_VIDEO_MODELS", str(tmp_path))
    seen = []
    monkeypatch.setattr(S, "MODEL_SHA256", __import__("hashlib").sha256(b"model").hexdigest())

    def fake(url, dst):
        seen.append(dst.name)
        with open(dst, "wb") as f:
            f.write(b"model")

    monkeypatch.setattr(S.urllib.request, "urlretrieve", fake)
    S.ensure_model(force=True)
    S.ensure_model(force=True)
    assert len(set(seen)) == 2 and (tmp_path / S.MODEL_NAME).read_bytes() == b"model"
