#!/usr/bin/env bash
# One-command local setup: Python 3.11 venv, FamiStudio 4.5.2, .NET 8, ffmpeg.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FAMISTUDIO_VERSION="4.5.2"
FAMISTUDIO_ZIP_URL="https://github.com/BleuBleu/FamiStudio/releases/download/${FAMISTUDIO_VERSION}/FamiStudio452-LinuxAMD64.zip"
STEMS=0
for arg in "$@"; do
  case "$arg" in
    --stems) STEMS=1 ;;
    -h|--help)
      echo "Usage: ./setup.sh [--stems]"
      echo "  --stems   also install Demucs + CPU PyTorch (large download)"
      exit 0
      ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }

echo "==> 检查 ffmpeg"
if ! have ffmpeg; then
  if have sudo; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq ffmpeg libsndfile1 fonts-noto-cjk
  else
    echo "请先安装 ffmpeg" >&2
    exit 1
  fi
fi

echo "==> 查找 Python 3.9–3.11（basic-pitch / TensorFlow 不支持 3.12+）"
PY=""
for cand in python3.11 python3.10 python3.9; do
  if have "$cand"; then PY="$cand"; break; fi
done
if [[ -z "$PY" ]]; then
  if have sudo; then
    sudo apt-get update -qq
    if ! sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev; then
      sudo apt-get install -y -qq software-properties-common
      sudo add-apt-repository -y ppa:deadsnakes/ppa
      sudo apt-get update -qq
      sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
    fi
    PY=python3.11
  else
    echo "需要 Python 3.9、3.10 或 3.11" >&2
    exit 1
  fi
fi
echo "    使用 $($PY --version)"

echo "==> 安装 .NET 8 运行时（FamiStudio 需要）"
if ! have dotnet || ! dotnet --list-runtimes 2>/dev/null | grep -q "Microsoft.NETCore.App 8"; then
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
  bash /tmp/dotnet-install.sh --channel 8.0 --runtime dotnet --install-dir "${HOME}/.dotnet"
  export PATH="${HOME}/.dotnet:${PATH}"
  export DOTNET_ROOT="${HOME}/.dotnet"
fi
# Persist for later shells if missing
if ! grep -q 'DOTNET_ROOT' "${HOME}/.profile" 2>/dev/null; then
  {
    echo 'export DOTNET_ROOT="$HOME/.dotnet"'
    echo 'export PATH="$HOME/.dotnet:$PATH"'
  } >> "${HOME}/.profile"
fi

echo "==> 下载 FamiStudio ${FAMISTUDIO_VERSION} Linux AMD64"
mkdir -p "${ROOT}/third_party"
if [[ ! -f "${ROOT}/third_party/FamiStudio/FamiStudio.dll" ]]; then
  curl -L --fail -o /tmp/FamiStudio-linux.zip "$FAMISTUDIO_ZIP_URL"
  rm -rf "${ROOT}/third_party/FamiStudio"
  unzip -q -o /tmp/FamiStudio-linux.zip -d "${ROOT}/third_party/FamiStudio"
fi

echo "==> 创建 venv 并安装 Python 依赖（pinned）"
if have uv; then
  uv venv -p "$PY" "${ROOT}/.venv"
  # setuptools<81 must be present before resampy imports pkg_resources
  uv pip install --python "${ROOT}/.venv/bin/python" "setuptools==80.9.0" "numpy==1.26.4"
  uv pip install --python "${ROOT}/.venv/bin/python" -r "${ROOT}/requirements.txt"
  uv pip install --python "${ROOT}/.venv/bin/python" -e "${ROOT}"
else
  "$PY" -m venv "${ROOT}/.venv"
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
  python -m pip install -U "pip" "setuptools==80.9.0" "wheel"
  python -m pip install "numpy==1.26.4"
  python -m pip install -r "${ROOT}/requirements.txt"
  python -m pip install -e "${ROOT}"
fi

if [[ "$STEMS" -eq 1 ]]; then
  echo "==> 安装 Demucs + CPU PyTorch"
  if have uv; then
    uv pip install --python "${ROOT}/.venv/bin/python" \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --index-strategy unsafe-best-match \
      -r "${ROOT}/requirements-stems.txt"
  else
    python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu \
      -r "${ROOT}/requirements-stems.txt"
  fi
fi

echo
echo "安装完成。"
echo "  source .venv/bin/activate"
echo "  export DOTNET_ROOT=\"\$HOME/.dotnet\" PATH=\"\$HOME/.dotnet:\$PATH\""
echo "  audio2fami samples/gymnopedie_30s.wav -f mp3 -o artifacts/out.mp3 --duration 25"
echo "  audio2fami ui --port 43187"
