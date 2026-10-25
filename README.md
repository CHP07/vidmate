# StoryVerse

**An AI story-to-video system.** A story goes in; a rendered MP4 comes out.

The pipeline: **Python orchestration + AI generation → HyperFrames compositions (HTML/CSS/GSAP) → MP4.**
Videos are plain web pages driven by one seekable GSAP timeline, so a headless
browser can screenshot every frame deterministically and FFmpeg can encode them.

Everything — dependencies, caches, renders — stays inside this folder. Nothing is
installed globally, nothing is written to `C:\` or your home directory.

---

## Requirements

| | Version | Why |
|---|---|---|
| Node.js | ≥ 22 | HyperFrames CLI |
| Python | 3.10+ (3.13 tested) | Orchestration layer |
| Google Chrome | any recent | Frames are screenshotted from it |
| Git | any | Clone |

**Tested on Windows** (Git Bash). `scripts/hf-runner.js` itself is
cross-platform, but `scripts/env.sh` and `scripts/verify_setup.py` still assume
the Windows layout (`.venv/Scripts`, `*.exe`) — on macOS/Linux swap in
`.venv/bin/` and expect to port those two helpers before `npm run verify` passes.

---

## Setup (from a fresh clone)

```bash
git clone https://github.com/CHP07/vidmate.git
cd vidmate
```

**1. Install the HyperFrames CLI (local, ~1 min)**

```bash
npm ci
```

**2. Create the Python environment and install deps (~30 s)**

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

**3. Fetch FFmpeg + FFprobe into `tools/ffmpeg/` (~30 s, one-time)**

The binaries are gitignored; this downloads them once and copies them where the
CLI expects:

```bash
.venv/Scripts/python -c "import os, shutil, static_ffmpeg.run as ff; a, b = ff.get_or_fetch_platform_executables_else_raise(); os.makedirs('tools/ffmpeg', exist_ok=True); shutil.copy(a, 'tools/ffmpeg'); shutil.copy(b, 'tools/ffmpeg')"
```

**4. Download the headless browser (~270 MB, one-time)**

```bash
node scripts/hf-runner.js browser ensure
```

**5. Verify everything**

```bash
npm run verify
```

Last line must be `Environment ready.`

> `npm run verify` runs `python` — if your shell has no `python`, activate the
> venv first (`source .venv/Scripts/activate`) or run
> `.venv/Scripts/python scripts/verify_setup.py`.

---

## Make your first video

```bash
# 1. Scaffold a project (pick any name)
node scripts/hf-runner.js init videos/my-first-video --non-interactive

# 2. Repoint its npm scripts at the local runner — init writes `npx`-based
#    scripts, which would skip the sandbox and write caches outside the project:
sed -i.bak 's|npx --yes hyperframes@[0-9.]*|node ../../scripts/hf-runner.js|' videos/my-first-video/package.json
rm -f videos/my-first-video/package.json.bak
cd videos/my-first-video
npm pkg set scripts.snapshot="node ../../scripts/hf-runner.js snapshot"

# 3. Write your scene in index.html:
#    - HTML/CSS layout, 1920×1080
#    - one paused GSAP timeline registered on window.__timelines["main"]
#    - data-start / data-duration on every timed element
#    - deterministic only: no Date.now(), no Math.random()

# 4. Gate: lint + runtime + layout + motion + contrast (must say "Check passed")
npm run check

# 5. Look at frames before rendering — the check cannot see aesthetics
npm run snapshot -- --at 1,3,5,7

# 6. Render  →  videos/my-first-video/renders/my-first-video_<timestamp>.mp4
npm run render
```

To watch your scene live while editing, run `npm run dev` — the HyperFrames
studio opens with playback controls. Opening `index.html` directly in a browser
shows frame 0 only (the timeline starts paused); append `.play()` to the final
`tl.seek(0)` call if you want it to self-play without the studio. The renderer
seeks the timeline to an exact time per frame — it never relies on wall-clock.

### Included examples

| Project | What it shows |
|---|---|
| `videos/bouncing-ball` | Physics-driven motion: squash & stretch, impact FX, deterministic bounce schedule |
| `videos/lighthouse` | 40 s multi-scene story |
| `videos/my-video` | 30 s five-scene example (content-level check warnings remain) |

---

## How it fits together

```
story / script  ──►  composition (index.html)  ──►  npm run check  ──►  npm run render
  (Python layer)        HTML + CSS + GSAP           lints it           headless Chrome
                        one seekable timeline                            screenshots → FFmpeg → MP4
```

- **Compositions** are self-contained HTML files — no build step. The renderer
  seeks the registered timeline to an exact time per frame, so every frame must
  be a pure function of time (no `Date.now()`, no `Math.random()`).
- **`scripts/hf-runner.js`** is the single CLI entry point. It runs the
  project-local `hyperframes` (no global install), puts `tools/ffmpeg` on PATH,
  and redirects every cache the engine would normally write to `C:\` into
  `.cache/` (see table below). Use it from anywhere in the repo:
  `node scripts/hf-runner.js <command>`.
- **Inside a video project**, the `npm run check/snapshot/render` scripts call
  this runner (the included examples are already wired; for a fresh scaffold,
  repoint them as shown in step 2 above).

---

## Project structure

```
vidmate/
├─ package.json          # hyperframes pinned as a local dependency
├─ package-lock.json
├─ requirements.txt      # Python deps (venv only)
├─ .venv/                # Python environment            ─┐
├─ node_modules/         # HyperFrames CLI + deps         ─┤ all gitignored,
├─ tools/ffmpeg/         # ffmpeg.exe + ffprobe.exe       ─┤ created by setup
├─ .cache/               # every engine cache & sandbox   ─┘
├─ scripts/
│  ├─ hf-runner.js       # sandboxed CLI launcher (use this)
│  ├─ env.sh             # PATH + cache exports for bash shells
│  └─ verify_setup.py    # environment health check (npm run verify)
├─ python/storyverse/    # orchestration package (in progress)
├─ videos/               # one HyperFrames project per video
├─ assets/               # shared media (fonts, images, audio)
├─ renders/              # extra MP4 output (each project also renders into its own renders/, all gitignored)
└─ README.md / .gitignore
```

---

## Where the engine writes (all inside this folder)

| Default location | Redirected to |
|---|---|
| `~\.cache\hyperframes\history` | `.cache/hyperframes/history` |
| `%TEMP%\hyperframes-extract-cache-*` | `.cache/hyperframes/extract` |
| `~\.cache\hyperframes\fonts` | `.cache/hyperframes/fonts` |
| `~\.hyperframes` (config, install state) | `.cache/user/.hyperframes` |
| `~`-derived paths (bundled browser, TTS models, stray `AppData` mkdirs) | `.cache/user/…` |
| `%APPDATA%` / `%LOCALAPPDATA%` / `%TEMP%` | `.cache/AppData/…`, `.cache/tmp` |

All of it is applied by `scripts/hf-runner.js` (and mirrored in
`scripts/env.sh` + `scripts/verify_setup.py`). Delete `.cache/` any time — it
rebuilds on demand.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `verify` fails on ffmpeg/ffprobe | Re-run step 3 |
| `verify` fails on Chrome / browser errors during render | Re-run step 4 |
| `hyperframes doctor` reports a new version available | Harmless — the pin is intentional; upgrade with `npx hyperframes@latest upgrade --project .` when you choose to |
| Shell can't find `python` | Use `.venv/Scripts/python …` or activate the venv |
| Fonts fetched from Google on first check | Needs network once; they're cached in `.cache/hyperframes/fonts` |

---

## Status & roadmap

**Working today:** scaffold → author → check → snapshot → render, fully local.

**Next:**
- Python orchestration: story → script → scene breakdown → composition generation
- AI integration: illustrations, TTS voiceover, SFX (`hyperframes doctor` flags
  Kokoro TTS and whisper-cpp as optional pip-installable components)
- Registry blocks (`node scripts/hf-runner.js catalog`) for reusable scenes

Repo: https://github.com/CHP07/vidmate
