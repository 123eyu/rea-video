#!/usr/bin/env bash
# 把 rea-video skill 链接到常见 agent 的 skills 目录，并安装 CLI。可重复运行。
# PYTHON_BIN=python3.12 bash scripts/install_skill.sh   # 指定解释器
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ---- ffmpeg ----
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "⚠ 没找到 ffmpeg / ffprobe，rea-video 跑不起来。安装：macOS 'brew install ffmpeg'，Ubuntu/Debian 'sudo apt install ffmpeg'" >&2
fi

# ---- Python >= 3.10 ----
py_ok() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; }
PY="${PYTHON_BIN:-}"
if [ -z "$PY" ]; then
  for c in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then PY="$c"; break; fi
  done
fi
if [ -z "$PY" ] || ! py_ok "$PY"; then
  echo "✗ 需要 Python ≥ 3.10（当前 ${PY:-python3}: $("${PY:-python3}" --version 2>&1 || echo 未安装)）。" >&2
  echo "  macOS: brew install python@3.12；Ubuntu: sudo apt install python3.12 python3.12-venv；然后 PYTHON_BIN=python3.12 bash $0" >&2
  exit 1
fi

# rapidocr 依赖 opencv-python，和 rea-video 的 opencv-python-headless 共用 cv2 目录，后装的覆盖先装的。
# 只留 headless 一套：删掉 opencv-python 后强制重装 headless（删除会带走共用文件）。
dedupe_cv() {  # 参数：能跑 pip 的命令，如 python -m pip / pipx runpip rea-video
  if "$@" show opencv-python >/dev/null 2>&1; then
    "$@" uninstall -y opencv-python >/dev/null
    "$@" install --force-reinstall --no-deps "opencv-python-headless>=4.8,<5" >/dev/null
    echo "已去掉重复的 opencv-python，只保留 opencv-python-headless"
  fi
}

# ---- 安装 CLI：pip -> (系统 Python 不让装时) pipx -> 仓库内 .venv ----
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
if "$PY" -m pip install -e "$ROOT[ocr]" 2>&1 | tee "$log"; [ "${PIPESTATUS[0]}" -eq 0 ]; then
  dedupe_cv "$PY" -m pip
elif grep -qi "externally-managed" "$log"; then
  echo "系统 Python 不允许直接 pip 安装（PEP 668），改用隔离环境。" >&2
  if command -v pipx >/dev/null 2>&1; then
    pipx install --force --python "$PY" -e "$ROOT[ocr]"
    dedupe_cv pipx runpip rea-video
  else
    "$PY" -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/python" -m pip install -e "$ROOT[ocr]"
    dedupe_cv "$ROOT/.venv/bin/python" -m pip
    mkdir -p "$HOME/.local/bin"
    ln -sfn "$ROOT/.venv/bin/rea-video" "$HOME/.local/bin/rea-video"
    echo "已装到 $ROOT/.venv，命令链接到 ~/.local/bin/rea-video"
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "⚠ ~/.local/bin 不在 PATH 里，把它加进 shell 配置。" >&2 ;; esac
  fi
else
  echo "✗ pip 安装失败，见上面的输出。" >&2
  exit 1
fi

# ---- 链接 skill：只链到已经装了的 agent（都没装就链到 ~/.claude/skills） ----
targets=()
for home in "$HOME/.claude" "$HOME/.codex" "$HOME/.agents"; do
  [ -d "$home" ] && targets+=("$home/skills")
done
[ ${#targets[@]} -eq 0 ] && targets=("$HOME/.claude/skills")
for dir in "${targets[@]}"; do
  mkdir -p "$dir"
  dest="$dir/rea-video"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    # ln -sfn 遇到真实目录会把链接建到它里面，还报成功
    echo "⚠ $dest 是一个真实目录（旧的手动拷贝？），跳过。删掉或改名后重跑。" >&2
    continue
  fi
  ln -sfn "$ROOT/skills/rea-video" "$dest"
  echo "linked $dest"
done
echo "done. 试试：rea-video --help"
