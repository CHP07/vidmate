#!/usr/bin/env bash
# Source this from the project root to make all local tools visible:
#   source scripts/env.sh
# Adds the local FFmpeg binaries, the venv, and node_modules/.bin to PATH and
# forces the env-var-overridable HyperFrames caches into this project folder.
# Nothing here is global; it only affects the current shell (or subprocess env).
#
# For a fully sandboxed CLI invocation (including homedir()-derived paths like
# the config dir and bundled-browser cache), use the runner instead:
#   node scripts/hf-runner.js <hyperframes args...>

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$ROOT/tools/ffmpeg:$ROOT/.venv/Scripts:$ROOT/node_modules/.bin:$PATH"

HF_CACHE="$ROOT/.cache/hyperframes"
export HYPERFRAMES_HISTORY_ROOT="$HF_CACHE/history"
export HYPERFRAMES_EXTRACT_CACHE_DIR="$HF_CACHE/extract"
export HYPERFRAMES_FONT_CACHE_DIR="$HF_CACHE/fonts"

# Invokes the CLI with HOME/USERPROFILE overridden for the child process only,
# so every remaining homedir()-based path (config dir ~/.hyperframes, bundled
# browser cache, optional packages, TTS models) also lands in the project.
hf() {
  USERPROFILE="$ROOT/.cache/user" HOME="$ROOT/.cache/user" \
  APPDATA="$ROOT/.cache/AppData/Roaming" LOCALAPPDATA="$ROOT/.cache/AppData/Local" \
  TEMP="$ROOT/.cache/tmp" TMP="$ROOT/.cache/tmp" \
    "$ROOT/node_modules/.bin/hyperframes.cmd" "$@"
}
