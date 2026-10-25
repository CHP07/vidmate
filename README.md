# StoryVerse — AI Story-to-Video System

Automated pipeline for turning stories into cinematic animated videos:
**Python orchestration + AI integration → HyperFrames (HTML/CSS/GSAP) → rendered MP4.**

All dependencies are installed **locally in this project folder only** (npm packages in
`node_modules/`, Python packages in `.venv/`, binaries in `tools/ffmpeg/`). Nothing is
installed globally; run `npx hyperframes` only if the local install is missing.

## Stack

Engine caches are redirected into the project too — **nothing is written outside this
folder** (see “Caches & state” below).

| Layer | Tool | Where |
|---|---|---|
| Animation & rendering | HyperFrames CLI `0.8.193` (Node 22, headless Chrome + FFmpeg) | `node_modules/` |
| Video authoring | HTML/CSS/GSAP compositions (no build step) | `videos/<name>/` |
| FFmpeg/FFprobe 8.0.1 | static build (gyan.dev essentials, via pip packages) | `tools/ffmpeg/` |
| Orchestration (primary language) | Python 3.13 venv | `.venv/` |

## Requirements met (verified)

- **Node.js v22.11.0** — HyperFrames requires >= 22 ✓
- **FFmpeg 8.0.1 + FFprobe 8.0.1** — discovered via `tools/ffmpeg` on PATH ✓
- **Chrome** — system Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe` ✓
- **hyperframes doctor** — all required checks pass; optional components
  (whisper-cpp transcription, Kokoro TTS, MusicGen local music, Docker renderer)
  are intentionally not yet installed.

## Project structure

```
 StoryVerse/
 ├─ package.json          # Node project; "hyperframes" installed as a local dep
 ├─ requirements.txt      # Python deps (pip, project-local only)
 ├─ .venv/                # Python 3.13 virtual environment (gitignored)
 ├─ node_modules/         # npm deps incl. the hyperframes CLI (gitignored)
 ├─ tools/ffmpeg/         # local FFmpeg + FFprobe binaries (gitignored)
 ├─ .cache/               # HF caches & sandboxed home overlay (gitignored)
 │  ├─ hyperframes/       #   history, fonts, frame-extract cache
 │  ├─ user/              #   CLI config + browser cache + skill installs
 │  ├─ AppData/           #   APPDATA/LOCALAPPDATA sandbox
 │  └─ tmp/               #   TEMP/TMP for CLI processes
 ├─ scripts/              # launcher + env + verification helpers
 ├─ python/               # future Python orchestration code (primary language)
 ├─ videos/               # one HyperFrames project per story/video
 │  └─ demo/              # CLI-scaffolded starter project (blank centered template)
 ├─ assets/               # shared media: illustrations, fonts, footage, audio
 ├─ renders/              # rendered MP4 output
 └─ README.md / .gitignore
```

## Caches & state (everything stays in this directory)

HyperFrames defaults to writing history blobs to `~\.cache\hyperframes`, a frame
extract cache to `%TEMP%`, and config to `~\.hyperframes`. This project pins all
of them locally:

| Default location | Redirected to | Mechanism |
|---|---|---|
| `~\.cache\hyperframes\history` | `.cache/hyperframes/history` | `HYPERFRAMES_HISTORY_ROOT` |
| `%TEMP%\hyperframes-extract-cache-*` | `.cache/hyperframes/extract` | `HYPERFRAMES_EXTRACT_CACHE_DIR` |
| `~\.cache\hyperframes\fonts` | `.cache/hyperframes/fonts` | `HYPERFRAMES_FONT_CACHE_DIR` |
| `~\.hyperframes` (config, install state) | `.cache/user/.hyperframes` | `HOME`/`USERPROFILE` override in launcher |
| `~\.cache\hyperframes\{chrome,tts,optional}` and any other `~`-derived path (incl. stray `AppData/Roaming` mkdirs) | `.cache/user/…` | `HOME`/`USERPROFILE` override in launcher |
| `%APPDATA%` / `%LOCALAPPDATA%` / `%TEMP%` reads by CLI children | `.cache/AppData/…` / `.cache/tmp` | `APPDATA`/`LOCALAPPDATA`/`TEMP`/`TMP` override in launcher |

Use **`node scripts/hf-runner.js <args…>`** to invoke the CLI anywhere in this
repo — it applies every override plus `tools/ffmpeg` on PATH. Inside
`videos/demo`, the `npm run dev/check/render` scripts already call this runner
instead of `npx`. `source scripts/env.sh` exports the env-var versions and adds
local bins to PATH; `scripts/verify_setup.py` (the Python orchestration entry)
applies the same overrides when spawning the CLI, so future pipeline code stays
out of C: as well.

The `videos/demo` folder is the untouched official scaffold (used for the smoke test);
no scenes, animations, or story content have been created.

## How to run things

```bash
# From the project root — recommended CLI entry point (all caches stay local) `--non-interactive`
node scripts/hf-runner.js <command>

# Inside a video project
cd videos/demo
npm run check
npm run render       # renders to ../../renders/ by default via -o

# Python orchestration
source .venv/Scripts/activate
python scripts/verify_setup.py     # or: source scripts/env.sh && python scripts/verify_setup.py
```

Env note: HyperFrames discovers FFmpeg/FFprobe via PATH (`tools/ffmpeg`) and all
cache paths via the overrides above — both handled by `scripts/hf-runner.js` and
mirrored in `scripts/env.sh` / `verify_setup.py`.

## Next steps (not yet implemented)

- Python orchestration module: story → script → scenes → shot lists → captions.
- AI integration for illustration, voiceover/TTS and SFX (doctor flags Kokoro
  TTS and whisper-cpp as future optional installs — both pip-friendly).
- Per-story composition generator emitting HyperFrames HTML/GSAP.
