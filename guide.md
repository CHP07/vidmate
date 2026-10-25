# StoryVerse Developer Guide

StoryVerse turns a story or script into an MP4. The pipeline is:

```text
story / script
    -> HyperFrames composition (index.html: HTML, CSS, GSAP)
    -> Cartesia voiceover (embedded voiceover manifest -> WAV + word timings)
    -> check / snapshot
    -> headless Chrome captures frames -> FFmpeg encodes MP4
```

Every frame is a pure function of timeline time. There is no wall-clock
rendering, no runtime TTS, and no per-frame network dependency during render.

If you are an LLM writing a composition, read `reference.md` as well. It defines
the single-file `index.html` voiceover contract.

---

## 1. Requirements

| Requirement | Version / notes |
|---|---|
| Node.js | 22 or newer |
| Python | 3.10 or newer |
| Google Chrome | used by HyperFrames |
| FFmpeg / FFprobe | provided by the project setup |
| Cartesia key | required only for voiceover generation |

The setup steps are in `README.md`. Verify the environment with:

```powershell
npm run verify
```

Do not install dependencies globally. Use the project-local `.venv` and
`node_modules`.

---

## 2. Project layout

```text
videos/<video-id>/
  index.html                 # composition, GSAP timeline, embedded voiceover manifest
  meta.json                  # project metadata
  voiceover.lock.json        # generated audio cache (do not hand-edit)
  assets/
    audio/
      voiceover/
        vo-01.wav            # generated or supplied narration
  renders/                   # MP4 output
```

Shared helpers live at the repository root:

```text
scripts/hf-runner.js         # sandboxed HyperFrames CLI
scripts/voiceover.py         # voiceover CLI entry point
python/storyverse/voiceover.py
```

A video without an embedded `voiceover-manifest` is a valid silent video. A
video with a manifest must have valid audio for every segment.

The manifest lives directly in `index.html`:

```html
<!-- VO:MANIFEST:START -->
<script id="voiceover-manifest" type="application/json">{ ... }</script>
<!-- VO:MANIFEST:END -->
```

Legacy projects that still have a `voiceover.json` are read as a fallback when
no embedded manifest exists.

---

## 3. Render an existing video

From the repository root:

```powershell
node scripts/hf-runner.js check videos/lighthouse
node scripts/hf-runner.js snapshot videos/lighthouse --at 2,8
node scripts/hf-runner.js render videos/lighthouse
```

Or from inside the video folder:

```powershell
cd videos/lighthouse
npm run check
npx hyperframes snapshot --at 2,8
npm run render
```

Useful commands:

| Command | Purpose |
|---|---|
| `preview` | open the HyperFrames preview/Studio |
| `check` | lint, runtime, layout, motion, contrast |
| `snapshot` | PNG frames at chosen seconds |
| `render` | render to MP4 |
| `publish` | publish a shareable link |

For an agent-safe persistent preview:

```powershell
node scripts/hf-runner.js preview videos/lighthouse --background
node scripts/hf-runner.js preview --status
node scripts/hf-runner.js preview --stop
```

Always look at frames after editing. A passing check does not prove the video
looks correct.

---

## 4. Voiceover workflow

Voiceover is optional and manifest-driven. The manifest is the only source of
truth for what is spoken. Do not infer narration from captions, transcripts, or
file names.

### 4.1 Configure Cartesia keys

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Add one or more keys:

```dotenv
CARTESIA_API_KEYS=key1,key2,key3
```

Keys are tried in order. A `401`, `403`, `429`, or `5xx` response moves to the
next key. Other `4xx` responses fail immediately. `.env` is gitignored; never
commit keys.

`CARTESIA_API_KEY` is also accepted for a single key.

### 4.2 Commands

```powershell
# What needs synthesis?
.venv\Scripts\python.exe scripts\voiceover.py plan videos/lighthouse

# Generate missing/stale audio, write the lock, update index.html
.venv\Scripts\python.exe scripts\voiceover.py build videos/lighthouse

# Verify audio exists, is current, and fits its slot
.venv\Scripts\python.exe scripts\voiceover.py check videos/lighthouse
```

`build` is idempotent. It only calls Cartesia for segments whose text or voice
configuration changed, or whose audio file is missing.

### 4.3 What `build` does

1. Reads the `voiceover-manifest` block from `index.html`.
2. Compares each segment against `voiceover.lock.json`.
3. Calls Cartesia for missing or stale segments.
4. Collects the raw PCM stream and word timestamps from the Cartesia SSE API.
5. Writes `assets/audio/voiceover/<segment-id>.wav`.
6. Writes `voiceover.lock.json`.
7. Replaces the marked blocks in `index.html`:
   - `VO:AUDIO` with `<audio>` tags
   - `VO:MANIFEST` with the resolved audio paths and word timings

TTS never runs during render. Render uses the generated audio and lock.

### 4.4 Editing narration

Change the segment `text` in the embedded manifest in `index.html` and run
`build` again. Only that line is regenerated.

Changing the voice configuration invalidates every segment. Changing `start` or
`slot` does not re-synthesize audio, but it does update the injected timing; run
`build` again and then `check`.

If a line exceeds its slot, the build fails with the segment ID and measured
duration. Fix it by shortening the text or lengthening the scene. Do not speed up
the audio in the composition.

### 4.5 Missing keys and missing audio

- No embedded manifest: the video is silent.
- Manifest exists with no lock/audio: `build` fails with a key error.
- Lock exists but audio is missing: `check` fails.
- Text or voice changed since the lock: `check` reports the segment as stale.
- Render does not require Python; it only needs the WAVs and the manifest already
  embedded in `index.html`.

Keep the build output (`voiceover.lock.json` and WAVs) if you want reproducible
renders without calling Cartesia again.

---

## 5. Create a new video

1. Scaffold a project as described in `README.md`.
2. Write `index.html` using the rules in `reference.md`.
3. Add the two marker blocks:
   - `VO:AUDIO`
   - `VO:MANIFEST`
4. Add the embedded `voiceover-manifest` if the video is narrated.
5. Run `voiceover build`.
6. Run `check`, `snapshot`, and inspect the frames.
7. Render only after the preview is approved.

A manifest is optional. If the video has no narration, omit it and do not run the
voiceover commands.

---

## 6. Timing model

For narrated videos, the voice is the clock:

- Each segment has a `start` and a `slot`.
- Audio must fit inside its slot.
- Scenes should start at the same time as their narration segment.
- Captions should use the same text and timing as the manifest.
- Word timings from Cartesia are relative to the segment audio. The
  composition adds the segment `start`.

For hand-authored videos with fixed scene durations, validate that each line
fits. For generated videos, derive scene boundaries from resolved audio
durations. Do not stretch visual motion to hide overlong audio.

---

## 7. Checks and output

Recommended sequence before delivery:

```powershell
.venv\Scripts\python.exe scripts\voiceover.py check videos/lighthouse
node scripts/hf-runner.js check videos/lighthouse
node scripts/hf-runner.js snapshot videos/lighthouse --at 2,8,16,24,34
node scripts/hf-runner.js render videos/lighthouse
```

Rendered files go to `videos/<video-id>/renders/` or the path passed with
`--output`.

Check the rendered audio is present and in range:

```powershell
node scripts/hf-runner.js audio videos\lighthouse\renders\<file>.mp4 --json
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `needs voice.provider cartesia` | Set `voice.provider` to `cartesia` in the embedded manifest |
| `set CARTESIA_API_KEYS...` | Add keys to `.env` or the environment |
| `all Cartesia keys failed` | Check key validity, quota, and network; the last provider error is printed |
| `vo-XX is X.XXs but its slot is Y.YYs` | Shorten the line or extend the scene |
| `vo-XX has no generated audio` | Run `voiceover build` |
| `vo-XX is stale` | Text or voice changed; run `voiceover build` |
| `index.html is missing the VO:AUDIO markers` | Restore both marker blocks exactly |
| No audio in the render | Check `voiceover.lock.json`, WAV paths, and that the audio tags are inside `#root` |
| Captions highlight evenly instead of with speech | Word counts differ or the manifest has no `words`; rebuild and inspect the `VO:MANIFEST` block |
| Preview shows only frame 0 | The timeline is paused by design; use the preview/Studio or seek the timeline |

`videos/lighthouse/index.html` is the reference example for the single-file
voiceover layout. New compositions should follow `reference.md` and keep the
manifest, caption hosts, and audio tags in sync.

---

## 9. Production rules

1. The embedded `voiceover-manifest` is the only narration source.
2. Segment IDs join text, audio, captions, and timeline placement.
3. No manifest means silence, not guessed audio.
4. A manifest means every segment must resolve and fit.
5. TTS runs before composition generation, never during render.
6. Audio is cached by text + voice configuration.
7. Keys live in `.env` or the environment, never in the embedded manifest or logs.
8. Keep each video isolated; one video's missing audio must not break another.
9. Cartesia is the only provider wired today. Other providers are future
   extension points, not current options.
10. Do not use the OpenAI SDK for Cartesia; use the Cartesia SSE API that
    `voiceover.py` already implements.

---

## 10. Extending the engine

The provider boundary is `_request()` and `_synthesize()` in
`python/storyverse/voiceover.py`. To add another provider later:

1. Add provider configuration to the manifest.
2. Add a request function with the same result shape: audio bytes and word
   timings.
3. Select the provider before synthesis.
4. Keep the lock format unchanged.

Do not add provider-specific logic to `index.html`. The composition only sees
generated `<audio>` tags and the embedded manifest.
