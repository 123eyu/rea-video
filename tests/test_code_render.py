"""Code-drawn pictures beyond particles: gradients, glass cards, neon, procedural colour fields, grain over flat design.
They have no material texture, which separates them from footage, AI video and 3D renders."""
import cv2
import numpy as np

from rea_video.classify import deterministic
from rea_video.features import spatial_features
from rea_video.plan import code_style
from rea_video.shots import _steady_morph


def _feat(img):
    f = spatial_features(img)
    # whole-frame motion, no frozen background: the case where a rendered picture is easily taken for a 3D render
    f.update({"dup_ratio": 0.0, "moving_pair_ratio": 1.0, "camera": "static", "temporal_noise": 0.5, "zero_pixel_ratio": 0.6})
    return f


def _gradient_blobs(shift=0.0):
    yy, xx = np.mgrid[0:480, 0:270].astype(np.float32)
    img = np.zeros((480, 270, 3), np.float32) + (255, 230, 240)
    for colour, x, y in (((107, 107, 255), 60, 120), ((255, 150, 77), 200, 250), ((61, 217, 255), 90, 400)):
        a = 0.85 * np.exp(-((xx - x - shift) ** 2 + (yy - y) ** 2) / (2 * 70.0 ** 2))[..., None]
        img = img * (1 - a) + np.array(colour, np.float32) * a
    return img.astype(np.uint8)


def _neon():
    img = np.full((480, 270, 3), (12, 2, 8), np.uint8)
    glow = np.zeros_like(img)
    cv2.putText(glow, "AI", (50, 270), cv2.FONT_HERSHEY_DUPLEX, 4, (214, 43, 255), 8, cv2.LINE_AA)
    img = cv2.add(img, cv2.GaussianBlur(glow, (0, 0), 8))
    return cv2.add(img, glow)


def _grain_poster(seed=0):
    img = np.full((480, 270, 3), (196, 220, 232), np.uint8)
    cv2.circle(img, (135, 170), 100, (61, 85, 200), -1, cv2.LINE_AA)
    img[330:] = (71, 48, 45)
    noise = np.random.default_rng(seed).normal(0, 2, img.shape[:2])[..., None]  # rendered posters measure sigma ~0.6; sigma >= 3 is not seen through
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def _textured_photo(seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:480, 0:270]
    shade = 90 + 80 * np.cos(xx / 60.0) * np.sin(yy / 90.0)  # lit surfaces
    fabric = cv2.GaussianBlur(rng.normal(0, 14, (480, 270)), (0, 0), 0.8)  # material texture
    base = np.clip(shade + fabric, 0, 255)
    return np.dstack([base * 0.8, base * 0.9, base]).astype(np.uint8)


def test_vector_fills_are_code_render():
    for name, img in (("gradient", _gradient_blobs()), ("neon", _neon()), ("grain", _grain_poster())):
        f = _feat(img)
        probs, ev, facts = deterministic(f)
        assert facts["vector_fill"] > 0.5, (name, f["tex_fine"], facts)
        assert max(probs, key=probs.get) == "code_render", (name, probs)
        assert any("纹理" in e for e in ev)


def _ink_lines(seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((480, 270, 3), (240, 247, 250), np.uint8)
    for _ in range(150):  # generative flow strokes on paper
        x, y = rng.uniform(0, 270), rng.uniform(0, 480)
        pts = []
        for _ in range(30):
            a = np.sin(x / 40.0) * 2 + np.cos(y / 55.0)
            x, y = x + 2 * np.cos(a), y + 2 * np.sin(a)
            pts.append((int(x), int(y)))
        cv2.polylines(img, [np.array(pts, np.int32)], False, (90, 60, 40), 1, cv2.LINE_AA)
    return img


def test_line_art_on_light_ground_is_code_render():
    f = _feat(_ink_lines())
    probs, ev, facts = deterministic(f)
    assert facts["fine_light"] > 0.5, {k: f[k] for k in ("light_ratio", "ink_ratio", "ink_smooth", "ink_peaks")}
    assert max(probs, key=probs.get) == "code_render"


def test_grainy_dark_ground_is_not_neon():
    img = _neon().astype(np.float32)
    img += np.random.default_rng(1).normal(0, 4, img.shape[:2])[..., None] * (img.mean(2, keepdims=True) < 40)
    f = _feat(np.clip(img, 0, 255).astype(np.uint8))
    assert f["dark_flat"] < 0.5
    _, _, facts = deterministic(f)
    assert facts["vector_fill"] < 0.3


def test_textured_picture_is_not_vector():
    f = _feat(_textured_photo())
    assert f["tex_fine"] > 0.15
    probs, _, facts = deterministic(f)
    assert facts["vector_fill"] < 0.2
    assert probs["code_render"] < 0.3


def test_code_style_names_the_build():
    def shot(facts, texts=()):
        return {"deterministic": {"facts": facts}, "text": {"tracks": [{"kind": "title", "texts": list(texts)}], "text_coverage": 0.01,
                                                             "items": [{"text": t, "conf": 0.95} for t in texts]}}
    assert code_style(shot({"fine_dark": 0.9})) == "particles"
    assert code_style(shot({"fine_light": 0.9})) == "lineart"
    assert code_style(shot({"vector_kind": "neon"})) == "neon"
    assert code_style(shot({"vector_kind": "gradient"})) == "gradient"
    assert code_style(shot({}, ["82", "610", "470", "抖音"])) == "data"
    assert code_style(shot({})) == "shapes"
    assert code_style(shot({}, ["000", "0", "00"])) == "shapes"  # zeros read off shapes are OCR noise


def test_colour_morph_is_not_a_dissolve():
    morph = [cv2.cvtColor(_gradient_blobs(3.0 * t), cv2.COLOR_BGR2GRAY) for t in range(40)]
    assert _steady_morph(morph, 20, 4)
    a, b = morph[0], cv2.cvtColor(_neon(), cv2.COLOR_BGR2GRAY)
    fade = [a] * 16 + [(a * (1 - w) + b * w).astype(np.uint8) for w in np.linspace(0, 1, 9)] + [b] * 16
    assert not _steady_morph(fade, 20, 4)
