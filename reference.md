# LLM Reference: `index.html` (single-file voiceover)

Read this before writing or modifying a StoryVerse composition. It is the
contract used by the voiceover builder and by HyperFrames.

If you only need to render an existing video, read `guide.md`.

---

## 1. Hard rules

1. Every video is one HyperFrames project under `videos/<video-id>/`.
2. `index.html` contains one root composition and one registered, paused GSAP
   timeline.
3. Every timed visual element has `class="clip"`, `data-start`, and
   `data-duration`.
4. Never tween `display`, `visibility`, or `autoAlpha` on an element with
   `class="clip"`. Animate a child instead.
5. Never call `play()`, `pause()`, or seek audio/video from composition code.
6. Never generate TTS audio in `index.html`.
7. The embedded `voiceover-manifest` in `index.html` is the only source of truth
   for spoken text and timing.
8. Hand-edit `text`, `start`, `slot`, `captionId`, `sceneId`, and `color` inside
   `VO:MANIFEST`. Do not hand-edit `audio`, `duration`, or `words`; the build owns
   those fields.
9. Keep all media paths project-relative, such as
   `assets/audio/voiceover/vo-01.wav`.
10. Use deterministic code only. No `Date.now()`, unseeded `Math.random()`, or
    network fetches.

---

## 2. Files

| File | Owner | Purpose |
|---|---|---|
| `index.html` | author / LLM | Composition, timeline, caption hosts, embedded manifest, marker blocks |
| `voiceover.lock.json` | `voiceover build` | Generated audio cache: hashes, paths, durations, word timings |
| `assets/audio/voiceover/*.wav` | `voiceover build` | Generated or supplied narration |
| `meta.json` | author | Video metadata |

The manifest lives in `index.html` between the `VO:MANIFEST` markers:

```html
<!-- VO:MANIFEST:START -->
<script id="voiceover-manifest" type="application/json">
{ "videoId": "video-id", "voice": { ... }, "segments": [ ... ] }
</script>
<!-- VO:MANIFEST:END -->
```

If no embedded manifest exists, the builder falls back to `voiceover.json` in the
project root for legacy projects. If neither exists, the video is silent.

---

## 3. `voiceover-manifest`

### 3.1 Shape

```json
{
  "schemaVersion": 1,
  "videoId": "video-id",
  "duration": 40,
  "voice": {
    "provider": "cartesia",
    "voiceId": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
    "modelId": "sonic-3.6",
    "language": "en",
    "settings": {
      "speed": 1.05
    }
  },
  "segments": [
    {
      "id": "vo-01",
      "captionId": "cap1",
      "sceneId": "scene1",
      "start": 0,
      "slot": 6,
      "text": "Midnight. A black sea.",
      "color": "#ffc65c",
      "audio": "assets/audio/voiceover/vo-01.wav",
      "duration": 5.6,
      "words": [
        { "text": "Midnight.", "start": 0.08, "end": 0.51 }
      ]
    }
  ]
}
```

`color`, `audio`, `duration`, and `words` are written by `voiceover build`; author
the other fields by hand.

### 3.2 Fields

| Field | Required | Meaning |
|---|---|---|
| `schemaVersion` | no | Currently informational |
| `videoId` | yes | Must match the project |
| `duration` | no | Root video duration; used to reject segments past the end |
| `voice.provider` | yes | Must be `cartesia` |
| `voice.voiceId` | yes | Cartesia voice ID |
| `voice.modelId` | no | Defaults to `sonic-3.6` |
| `voice.language` | no | Defaults to `en` |
| `voice.settings` | no | Passed to Cartesia `generation_config`; supports `volume`, `speed`, `emotion` |
| `segments[].id` | yes | Stable unique ID; also the audio filename |
| `segments[].captionId` | recommended | Caption `div` ID without `#` |
| `segments[].sceneId` | recommended | Authoring anchor for the scene |
| `segments[].start` | yes | Absolute start time in seconds |
| `segments[].slot` | yes | Reserved duration in seconds |
| `segments[].text` | yes | Exact text sent to TTS and used for captions |
| `segments[].color` | no | Caption highlight color; defaults to `#ffc65c` |
| `segments[].audio` | build | Generated WAV path |
| `segments[].duration` | build | Measured audio duration |
| `segments[].words` | build | Word timings relative to segment audio |

Rules:

- Segment IDs must be unique and stable. Prefer `vo-01`, `vo-02`, ...
- `captionId` must match the caption element's `id` without `#`. If omitted, it
  defaults to the segment `id`, which usually does not match a caption div.
- `start + slot` must not exceed `duration` when `duration` is present.
- Audio must fit inside `slot` with a 0.01 s tolerance.
- Do not put API keys in the manifest. Keys live in `.env` or the environment.
- Use only the fields above; only Cartesia is wired.

### 3.3 Editing behavior

The cache key is `voice + text`. Therefore:

- Changing `text` or `voice` makes that segment stale and regenerates it.
- Changing `start`, `slot`, or `captionId` does not call Cartesia; run `build`
  again to re-inject the new timing.
- Removing a segment drops it from the generated lock, but does not delete its
  old WAV automatically.

---

## 4. `index.html`

### 4.1 Root

The root must declare the composition and duration:

```html
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="40"
     data-width="1080"
     data-height="1920">
```

Timed scenes and captions use the same start times as the narration segments.

### 4.2 Required voiceover markers

Place these exact comments in `index.html`.

Inside the root composition:

```html
<!-- VO:AUDIO:START -->
<!-- VO:AUDIO:END -->
```

Outside the root composition, before the main `<script>`:

```html
<!-- VO:MANIFEST:START -->
<script id="voiceover-manifest" type="application/json">{ ... }</script>
<!-- VO:MANIFEST:END -->
```

If a marker is missing, `voiceover build` fails rather than guessing.

### 4.3 Generated audio block

After `voiceover build`, the audio block looks like this:

```html
<audio id="vo-01"
       data-start="0"
       data-volume="1"
       data-voiceover="vo-01"
       src="assets/audio/voiceover/vo-01.wav"></audio>
```

Rules:

- One `<audio>` per segment.
- `id` equals the segment `id`.
- `data-start` equals the segment `start`.
- Omit `data-duration` so the full file plays.
- Every audio element needs an `id`.
- Do not add `crossorigin`.
- Do not create or move audio tags from JavaScript.
- Do not edit this block by hand.

### 4.4 Generated manifest data

After `voiceover build`, each segment in the embedded manifest carries its
resolved audio and word timings:

```json
{
  "id": "vo-01",
  "captionId": "cap1",
  "start": 0,
  "slot": 6,
  "text": "Midnight. A black sea.",
  "audio": "assets/audio/voiceover/vo-01.wav",
  "duration": 5.6,
  "words": [
    { "text": "Midnight.", "start": 0.08, "end": 0.51 }
  ]
}
```

Rules:

- Captions are joined by `captionId`, not the segment `id`.
- `start` is an absolute timeline second; `end` is `start + slot`.
- `word.start` and `word.end` are relative to the segment audio.
- Do not rename the script ID `voiceover-manifest`.
- Do not edit `audio`, `duration`, or `words` by hand.

### 4.5 Caption host elements

The caption element IDs must match `captionId`:

```html
<div id="cap1"
     class="clip caption"
     data-start="0"
     data-duration="6"
     data-track-index="2"
     aria-label="Midnight. A black sea."></div>
```

At initialization, read the embedded manifest and derive captions from its
segments:

```js
const manifestEl = document.getElementById("voiceover-manifest");
const VOICEOVER = manifestEl
  ? JSON.parse(manifestEl.textContent || "{}")
  : { segments: [] };

const captions = VOICEOVER.segments.map(segment => {
  const id = "#" + (segment.captionId || segment.id);
  const el = document.querySelector(id);
  const words = segment.text.split(/\s+/);

  el.setAttribute("aria-label", segment.text);
  el.textContent = "";
  words.forEach((word, i) => {
    const span = document.createElement("span");
    span.className = "word";
    span.textContent = word + (i === words.length - 1 ? "" : " ");
    el.appendChild(span);
  });

  return {
    id,
    text: segment.text,
    start: segment.start,
    end: segment.start + segment.slot,
    color: segment.color || "#ffc65c",
    timings: segment.words || []
  };
});
```

When word timings exist and the word counts match, highlight at the real times:

```js
const timings = c.timings;
if (timings.length === spans.length) {
  spans.forEach((span, i) => {
    const word = timings[i];
    const t = c.start + word.start;
    const back = Math.max(t + 0.02, c.start + word.end - 0.02);
    if (i > 0) tl.set(spans[i - 1], { color: "#f7f5ef", scale: 1 }, t);
    tl.to(span, { color: c.color, scale: 1.04, duration: 0.08 }, t);
    tl.to(span, { scale: 1, duration: 0.06 }, back);
  });
}
```

Keep an even-spacing fallback for silent videos or count mismatches. Do not rely
on the fallback when audio exists; fix the caption text so the word count matches.

### 4.6 Minimal skeleton

```html
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="40"
     data-width="1080"
     data-height="1920">

  <div id="scene1"
       class="clip scene"
       data-start="0"
       data-duration="6">
    <!-- scene content -->
  </div>

  <div id="cap1"
       class="clip caption"
       data-start="0"
       data-duration="6"
       data-track-index="2"
       aria-label="Midnight. A black sea."></div>

  <!-- VO:AUDIO:START -->
  <!-- VO:AUDIO:END -->
</div>

<!-- VO:MANIFEST:START -->
<script id="voiceover-manifest" type="application/json">{ ... }</script>
<!-- VO:MANIFEST:END -->

<script>
(function () {
  const tl = gsap.timeline({ paused: true });
  window.__timelines = window.__timelines || {};

  // build caption spans, scenes, and tweens here

  window.__timelines["main"] = tl;
  tl.seek(0);
  if (!window.__HYPERFRAMES_RENDERER__) tl.play(0);
})();
</script>
```

---

## 5. Timing rules

- `start` and `slot` in the manifest must match the scene and caption
  `data-start` / `data-duration`.
- A segment occupies `[start, start + slot)`.
- Audio plays from `start` and runs for its real duration.
- Word highlight time = `segment.start + word.start`.
- Do not use the audio duration as the scene duration. Keep the reserved slot.
- If audio is longer than its slot, change the text or the scene timing.
- Do not stretch, compress, or time-stretch narration in the composition.

Example mapping:

| Segment | Start | Slot | Scene | Caption |
|---|---:|---:|---|---|
| `vo-01` | 0 | 6 | `scene1` | `cap1` |
| `vo-02` | 6 | 8 | `scene2` | `cap2` |
| `vo-03` | 14 | 8 | `scene3` | `cap3` |
| `vo-04` | 22 | 10 | `scene4` | `cap4` |
| `vo-05` | 32 | 8 | `scene5` | `cap5` |

---

## 6. Build and validate

```powershell
.venv\Scripts\python.exe scripts\voiceover.py plan videos/<video-id>
.venv\Scripts\python.exe scripts\voiceover.py build videos/<video-id>
.venv\Scripts\python.exe scripts\voiceover.py check videos/<video-id>
```

Key behavior:

- `plan` prints `missing`, `stale`, or `fresh` per segment.
- `build` synthesizes only stale or missing segments.
- `build` writes the lock and replaces the marker blocks.
- `check` fails if a segment is missing, stale, missing its file, or over its
  slot.
- Keys are read from `CARTESIA_API_KEYS` or `CARTESIA_API_KEY`.
- `.env` at the repository root is loaded automatically.
- Cartesia returns raw PCM plus word timings; the builder wraps the PCM as WAV.

Provider behavior:

- Multiple keys are tried in order.
- `401`, `403`, `429`, and `5xx` fall through to the next key.
- Other `4xx` responses stop immediately.
- ElevenLabs is not supported.
- Do not use the OpenAI SDK for Cartesia.

---

## 7. Common failures

| Message | Cause | Fix |
|---|---|---|
| `voiceover-manifest is invalid JSON` | Broken embedded manifest | Fix the JSON inside `VO:MANIFEST` |
| `missing voiceover.json` | No embedded manifest and no legacy file | Add `VO:MANIFEST` or restore the legacy file |
| `segment is missing id, start, slot, text` | Incomplete segment | Fill every required field |
| `duplicate segment id` | Reused ID | Make IDs unique |
| `needs voice.provider cartesia` | Wrong provider | Set `"provider": "cartesia"` |
| `vo-XX runs past the video duration` | `start + slot > duration` | Fix timing or `duration` |
| `all Cartesia keys failed` | Bad keys, quota, or network | Check `.env` and provider error |
| `vo-XX is X.XXs but its slot is Y.YYs` | Audio too long | Shorten text or extend scene |
| `vo-XX has no generated audio` | Build not run | Run `voiceover build` |
| `vo-XX is stale` | Text or voice changed | Run `voiceover build` |
| `missing the VO:AUDIO markers` | Markers removed or renamed | Restore exact comments |
| `missing the VO:MANIFEST markers` | Manifest markers removed or renamed | Restore exact comments |
| Captions evenly spaced | Word count mismatch or no timings | Check `captionId`, text, and rebuild |
| No voice in render | Audio tags missing or outside root | Rebuild and keep audio inside `#root` |

---

## 8. LLM checklist

Before finishing a composition:

- [ ] The embedded manifest has `videoId`, `voice.provider: "cartesia"`, `voice.voiceId`, and unique segments.
- [ ] Every segment has `id`, `start`, `slot`, and `text`.
- [ ] Every segmented scene and caption starts at the same time.
- [ ] Every `captionId` matches a caption `div` ID without `#`.
- [ ] `VO:AUDIO` and `VO:MANIFEST` markers exist exactly once each.
- [ ] No hand-written `<audio>` tags outside the generated marker block.
- [ ] The caption hook reads `voiceover-manifest` and uses word timings when present.
- [ ] Caption `data-start` / `data-duration` and audio `data-start` match the manifest.
- [ ] The timeline is paused and registered on `window.__timelines["main"]`.
- [ ] No `autoAlpha`, `visibility`, or `display` tween targets a `.clip` element.
- [ ] No runtime TTS, network fetch, `Date.now()`, or unseeded randomness.
- [ ] `voiceover build` and `voiceover check` ran successfully.
- [ ] HyperFrames `check` ran; any remaining findings were reviewed.

`videos/lighthouse/index.html` is the reference example for the single-file
voiceover layout. Keep the manifest, caption hosts, and audio tags in sync; the
build rewrites only the generated fields.
