"""Small shared helpers: logging, JSON IO, env loading, time formatting."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Iterable

LOG = logging.getLogger("rea_video")
OCR_LANGS = ("zh", "ja")  # subtitle/huazi OCR languages; zh is the bundled recognizer, others are in overlay._REC_MODELS


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", stream=sys.stderr)


def write_json(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_default(value: Any) -> Any:
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except ImportError:  # pragma: no cover
        pass
    if isinstance(value, Path):
        return str(value)
    return str(value)


def load_env_files(paths: Iterable[str | Path]) -> list[str]:
    """Minimal .env loader (KEY=VALUE lines). Existing env vars win. Returns loaded files."""
    loaded: list[str] = []
    for raw in paths:
        if not raw:
            continue
        p = Path(raw).expanduser()
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        loaded.append(str(p))
    return loaded


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:06.3f}"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def round_floats(obj: Any, nd: int = 4) -> Any:
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, nd) for v in obj]
    try:
        import numpy as np

        if isinstance(obj, np.floating):
            return round(float(obj), nd)
        if isinstance(obj, np.integer):
            return int(obj)
    except ImportError:  # pragma: no cover
        pass
    return obj
