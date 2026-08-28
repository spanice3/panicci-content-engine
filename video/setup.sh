#!/usr/bin/env bash
# One-time environment setup for the Panicci talking-head video pipeline.
# Safe to re-run. Installs a static ffmpeg, Space Grotesk, python deps, and
# builds the brand assets (logo rasters + weighted fonts) into video/.build/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# --- ffmpeg (static build, no root needed beyond /usr/local/bin write) ---
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Installing static ffmpeg..."
  tmp="$(mktemp -d)"
  curl -fsSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" -o "$tmp/ff.tar.xz"
  tar xf "$tmp/ff.tar.xz" -C "$tmp"
  d="$(find "$tmp" -maxdepth 1 -type d -name 'ffmpeg-*-static')"
  cp "$d/ffmpeg" "$d/ffprobe" /usr/local/bin/
  rm -rf "$tmp"
fi
ffmpeg -version | head -1

# --- Space Grotesk variable font ---
mkdir -p .build
if [ ! -f .build/SpaceGrotesk-VF.ttf ]; then
  echo "Fetching Space Grotesk..."
  curl -fsSL "https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf" -o .build/SpaceGrotesk-VF.ttf
fi

# --- python deps ---
pip install -q -r requirements.txt

# --- build brand assets (logo rasters + weighted fonts, installs fonts) ---
python3 assets_build.py
echo "Setup complete."
