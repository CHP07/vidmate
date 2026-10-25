"""Cartesia voiceover build for HyperFrames videos.

The manifest is the source of truth. This module only synthesizes missing or
stale lines, writes a lock file, and injects the resulting audio tags plus
caption word timings into the composition.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

API_URL = "https://api.cartesia.ai/tts/sse"
API_VERSION = "2026-08-14"
SAMPLE_RATE = 44100
OUTPUT_FORMAT = {
    "container": "raw",
    "encoding": "pcm_s16le",
    "sample_rate": SAMPLE_RATE,
}
RETRYABLE = {401, 403, 429, 500, 502, 503, 504}
MANIFEST_RE = re.compile(
    r'<script\s+id="voiceover-manifest"[^>]*>(.*?)</script>', re.DOTALL
)


class VoiceoverError(RuntimeError):
    pass


class _RetryableKeyError(Exception):
    pass


def _sha(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _api_keys() -> list[str]:
    raw = os.environ.get("CARTESIA_API_KEYS", "")
    keys = [key.strip() for key in raw.replace("\n", ",").split(",") if key.strip()]
    single = os.environ.get("CARTESIA_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VoiceoverError(f"missing {path.name}") from None
    except json.JSONDecodeError as exc:
        raise VoiceoverError(f"{path.name} is invalid JSON: {exc}") from None


def _write_json(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_bytes(path: Path, value: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(value)
    tmp.replace(path)


def _format_manifest(manifest: dict) -> str:
    head = {key: value for key, value in manifest.items() if key != "segments"}
    lines = ["{"]
    for key, value in head.items():
        rendered = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ")
        lines.append(f'  "{key}": {rendered},')
    segments = manifest.get("segments") or []
    lines.append('  "segments": [')
    for index, segment in enumerate(segments):
        lines.append("    {")
        fields = list(segment.items())
        for field_index, (key, value) in enumerate(fields):
            if key == "words":
                rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            else:
                rendered = json.dumps(value, ensure_ascii=False)
            comma = "," if field_index < len(fields) - 1 else ""
            lines.append(f'      "{key}": {rendered}{comma}')
        lines.append("    }" + ("," if index < len(segments) - 1 else ""))
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines)


def _manifest_path(project: Path) -> Path:
    meta = project / "meta.json"
    if meta.exists():
        try:
            name = json.loads(meta.read_text(encoding="utf-8")).get("voiceover")
            if name:
                return project / name
        except (OSError, json.JSONDecodeError):
            pass
    return project / "voiceover.json"


def _embedded_manifest(project: Path) -> dict | None:
    path = project / "index.html"
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8")
    match = MANIFEST_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise VoiceoverError(f"voiceover-manifest is invalid JSON: {exc}") from None


def _manifest(project: Path) -> dict:
    manifest = _embedded_manifest(project)
    if manifest is None:
        manifest = _read_json(_manifest_path(project))
    segments = manifest.get("segments") or []
    if not manifest.get("videoId") or not manifest.get("voice") or not segments:
        raise VoiceoverError("voiceover manifest needs videoId, voice and segments")
    if manifest["voice"].get("provider") != "cartesia":
        raise VoiceoverError("voiceover manifest needs voice.provider cartesia")
    if not manifest["voice"].get("voiceId"):
        raise VoiceoverError("voiceover manifest needs voice.voiceId")

    seen = set()
    for segment in segments:
        missing = [key for key in ("id", "start", "slot", "text") if key not in segment]
        if missing:
            raise VoiceoverError(f"segment is missing {', '.join(missing)}")
        if segment["id"] in seen:
            raise VoiceoverError(f"duplicate segment id {segment['id']}")
        seen.add(segment["id"])

    duration = manifest.get("duration")
    if duration is not None:
        for segment in segments:
            if segment["start"] + segment["slot"] > duration:
                raise VoiceoverError(f"{segment['id']} runs past the video duration")
    return manifest


def _lock(project: Path) -> dict:
    path = project / "voiceover.lock.json"
    if not path.exists():
        return {"schemaVersion": 1, "segments": {}}
    return _read_json(path)


def _hash(voice: dict, text: str) -> str:
    return _sha({"voice": voice, "text": text})


def _words(event: dict) -> list[dict]:
    timestamps = event.get("word_timestamps") or {}
    words = timestamps.get("words") or []
    starts = timestamps.get("start") or []
    ends = timestamps.get("end") or []
    if not words or len(words) != len(starts) or len(words) != len(ends):
        return []
    return [
        {"text": str(word), "start": float(start), "end": float(end)}
        for word, start, end in zip(words, starts, ends)
    ]


def _wav(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)
    return buffer.getvalue()


def _duration(audio: bytes) -> float:
    with wave.open(io.BytesIO(audio), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def _request(text: str, voice: dict, key: str) -> tuple[bytes, list[dict]]:
    payload = {
        "model_id": voice.get("modelId") or "sonic-3.6",
        "transcript": text,
        "voice": voice["voiceId"],
        "output_format": OUTPUT_FORMAT,
        "language": voice.get("language") or "en",
        "add_timestamps": True,
    }
    if voice.get("settings"):
        payload["generation_config"] = voice["settings"]

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "X-API-Key": key,
            "Cartesia-Version": API_VERSION,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    audio = bytearray()
    words: list[dict] = []
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError as exc:
                    raise VoiceoverError("Cartesia returned invalid SSE data") from exc
                kind = event.get("type")
                if kind == "chunk":
                    try:
                        audio.extend(base64.b64decode(event.get("data") or ""))
                    except ValueError as exc:
                        raise VoiceoverError("Cartesia returned invalid audio") from exc
                elif kind == "timestamps":
                    words.extend(_words(event))
                elif kind == "error":
                    detail = (
                        f"{event.get('title') or 'error'}: "
                        f"{event.get('message') or 'unknown error'}"
                    )
                    code = event.get("status_code")
                    if code in RETRYABLE:
                        raise _RetryableKeyError(f"HTTP {code}: {detail}") from None
                    raise VoiceoverError(f"Cartesia rejected the request: {detail}")
                elif kind == "done":
                    break
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        if exc.code in RETRYABLE:
            raise _RetryableKeyError(f"HTTP {exc.code}: {body}") from None
        raise VoiceoverError(f"Cartesia rejected the request: HTTP {exc.code}: {body}") from None
    except urllib.error.URLError as exc:
        raise _RetryableKeyError(f"network error: {exc.reason}") from None

    if not audio:
        raise VoiceoverError("Cartesia returned no audio")
    if not words:
        raise VoiceoverError("Cartesia returned no word timings")
    return _wav(bytes(audio)), words


def _synthesize(text: str, voice: dict, keys: list[str]) -> tuple[bytes, list[dict]]:
    errors = []
    for key in keys:
        try:
            return _request(text, voice, key)
        except _RetryableKeyError as exc:
            errors.append(str(exc))
    detail = errors[-1] if errors else "no usable key"
    raise VoiceoverError(f"all Cartesia keys failed: {detail}")


def _segment(project: Path, manifest: dict, segment: dict, keys: list[str]) -> dict:
    voice = manifest["voice"]
    digest = _hash(voice, segment["text"])
    entry = {
        "hash": digest,
        "provider": "cartesia",
        "voiceId": voice["voiceId"],
        "modelId": voice.get("modelId"),
        "audio": f"assets/audio/voiceover/{segment['id']}.wav",
    }

    if not keys:
        raise VoiceoverError(
            "set CARTESIA_API_KEYS (comma-separated) or CARTESIA_API_KEY"
        )

    audio, words = _synthesize(segment["text"], voice, keys)
    duration = _duration(audio)
    if duration > segment["slot"] + 0.01:
        raise VoiceoverError(
            f"{segment['id']} is {duration:.2f}s but its slot is {segment['slot']:.2f}s; "
            "shorten the text or lengthen the scene"
        )

    path = project / entry["audio"]
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(path, audio)
    entry.update({"duration": round(duration, 3), "words": words})
    return entry


def _replace_block(html: str, name: str, content: str) -> str:
    pattern = re.compile(
        rf"(<!-- VO:{name}:START -->)(.*?)(<!-- VO:{name}:END -->)",
        re.DOTALL,
    )
    if not pattern.search(html):
        raise VoiceoverError(f"index.html is missing the VO:{name} markers")
    return pattern.sub(
        lambda match: f"{match.group(1)}\n{content}\n{match.group(3)}",
        html,
        count=1,
    )


def _audio_tags(manifest: dict, lock: dict) -> list[str]:
    tags = []
    for segment in manifest["segments"]:
        entry = lock["segments"][segment["id"]]
        tags.append(
            f'<audio id="{segment["id"]}" data-start="{segment["start"]}" '
            f'data-volume="1" data-voiceover="{segment["id"]}" '
            f'src="{entry["audio"]}"></audio>'
        )
    return tags


def _inject_embedded(project: Path, manifest: dict, lock: dict) -> None:
    path = project / "index.html"
    html = path.read_text(encoding="utf-8")
    updated = json.loads(json.dumps(manifest))

    for segment in updated["segments"]:
        entry = lock["segments"][segment["id"]]
        segment["audio"] = entry["audio"]
        segment["duration"] = entry["duration"]
        segment["words"] = entry["words"]

    data = _format_manifest(updated).replace("<", "\\u003c")
    block = (
        f'<script id="voiceover-manifest" type="application/json">\n'
        f"{data}\n</script>"
    )
    html = _replace_block(html, "MANIFEST", block)
    html = _replace_block(html, "AUDIO", "\n".join(_audio_tags(manifest, lock)))
    path.write_text(html, encoding="utf-8", newline="\n")


def _inject(project: Path, manifest: dict, lock: dict) -> None:
    path = project / "index.html"
    html = path.read_text(encoding="utf-8")
    if MANIFEST_RE.search(html):
        _inject_embedded(project, manifest, lock)
        return
    caption_data = {}

    for segment in manifest["segments"]:
        entry = lock["segments"][segment["id"]]
        caption_data[segment.get("captionId", segment["id"])] = {
            "text": segment["text"],
            "start": segment["start"],
            "end": segment["start"] + segment["slot"],
            "words": entry["words"],
        }

    data = json.dumps(caption_data, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    html = _replace_block(html, "AUDIO", "\n".join(_audio_tags(manifest, lock)))
    html = _replace_block(
        html,
        "DATA",
        f'<script id="voiceover-data" type="application/json">{data}</script>',
    )
    path.write_text(html, encoding="utf-8", newline="\n")


def build(project: Path) -> None:
    _load_dotenv()
    manifest = _manifest(project)
    lock = _lock(project)
    keys = _api_keys()
    entries = {}

    for segment in manifest["segments"]:
        previous = lock.get("segments", {}).get(segment["id"])
        digest = _hash(manifest["voice"], segment["text"])
        if (
            previous
            and previous.get("hash") == digest
            and previous.get("words")
            and (project / previous["audio"]).exists()
        ):
            entries[segment["id"]] = previous
            continue
        entries[segment["id"]] = _segment(project, manifest, segment, keys)

    resolved = {
        "schemaVersion": 1,
        "videoId": manifest["videoId"],
        "segments": entries,
    }
    _write_json(project / "voiceover.lock.json", resolved)
    _inject(project, manifest, resolved)
    print(f"voiceover: {len(entries)} segments ready")


def check(project: Path) -> None:
    manifest = _manifest(project)
    lock = _lock(project)
    for segment in manifest["segments"]:
        entry = lock.get("segments", {}).get(segment["id"])
        if not entry:
            raise VoiceoverError(f"{segment['id']} has no generated audio")
        if entry.get("hash") != _hash(manifest["voice"], segment["text"]):
            raise VoiceoverError(f"{segment['id']} is stale; run build")
        if entry.get("words") and len(entry["words"]) != len(segment["text"].split()):
            raise VoiceoverError(f"{segment['id']} word timings do not match its text")
        if not (project / entry["audio"]).exists():
            raise VoiceoverError(f"{segment['id']} audio file is missing")
        if entry.get("duration", 0) > segment["slot"] + 0.01:
            raise VoiceoverError(f"{segment['id']} does not fit its slot")
    print(f"voiceover: {len(manifest['segments'])} segments valid")


def plan(project: Path) -> None:
    manifest = _manifest(project)
    lock = _lock(project)
    result = []
    for segment in manifest["segments"]:
        entry = lock.get("segments", {}).get(segment["id"])
        if not entry:
            status = "missing"
        elif entry.get("hash") != _hash(manifest["voice"], segment["text"]):
            status = "stale"
        elif not (project / entry["audio"]).exists():
            status = "missing"
        else:
            status = "fresh"
        result.append({"id": segment["id"], "status": status, "text": segment["text"]})
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Cartesia voiceover for a HyperFrames video")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "check", "plan"):
        command = subparsers.add_parser(name)
        command.add_argument("project", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            build(args.project.resolve())
        elif args.command == "check":
            check(args.project.resolve())
        else:
            plan(args.project.resolve())
    except VoiceoverError as exc:
        print(f"voiceover: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
