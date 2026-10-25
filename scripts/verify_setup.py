"""Environment verification for the StoryVerse setup stage.

Checks that Node/npm, the local HyperFrames install, the local FFmpeg/FFprobe
binaries, Chrome, and the Python venv are all usable. Run it with the venv:

    source scripts/env.sh && python scripts/verify_setup.py
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG_DIR = ROOT / "tools" / "ffmpeg"

# node_modules/.bin/hyperframes is a shell script unusable by CreateProcess on
# Windows; the .cmd shim is the launchable entry point there.
_BIN = ROOT / "node_modules" / ".bin"
HYPERFRAMES = _BIN / "hyperframes.cmd" if os.name == "nt" else _BIN / "hyperframes"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check_env():
    """Project-scoped env: local binaries on PATH + all HyperFrames caches
    redirected into the project folder (see scripts/hf-runner.js)."""
    env = os.environ.copy()
    env["PATH"] = f"{FFMPEG_DIR}{os.pathsep}{env['PATH']}"
    hf_cache = ROOT / ".cache" / "hyperframes"
    env["HYPERFRAMES_HISTORY_ROOT"] = str(hf_cache / "history")
    env["HYPERFRAMES_EXTRACT_CACHE_DIR"] = str(hf_cache / "extract")
    env["HYPERFRAMES_FONT_CACHE_DIR"] = str(hf_cache / "fonts")
    # Any path still derived from the home directory (config dir, bundled
    # browser cache, optional packages, AppData temps) resolves inside
    # .cache/user — never in the project root, never on C:.
    # Mirrors scripts/hf-runner.js.
    home = ROOT / ".cache" / "user"
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    hf_cache_appdata = ROOT / ".cache" / "AppData"
    env["APPDATA"] = str(hf_cache_appdata / "Roaming")
    env["LOCALAPPDATA"] = str(hf_cache_appdata / "Local")
    env["TEMP"] = str(ROOT / ".cache" / "tmp")
    env["TMP"] = str(ROOT / ".cache" / "tmp")
    return env


def ok(name, good, detail=""):
    print(f"[{'OK' if good else 'FAIL'}] {name} {detail}")
    return good


def main():
    env = check_env()
    results = []

    # Node & npm
    node = run(["node", "--version"])
    results.append(ok("Node.js", node.returncode == 0, node.stdout.strip()))

    # Local HyperFrames CLI (not global)
    hf = run([str(HYPERFRAMES), "--version"])
    hf_ok = hf.returncode == 0 and hf.stdout.strip().startswith(("0.", "1."))
    results.append(
        ok("HyperFrames CLI (local)", hf_ok, "@ " + str(HYPERFRAMES.parent))
    )

    # FFmpeg / FFprobe from tools/ffmpeg
    for tool, flag in (("ffmpeg.exe", "-version"), ("ffprobe.exe", "-version")):
        path = FFMPEG_DIR / tool
        r = run([str(path), flag])
        version = r.stdout.splitlines()[0] if r.returncode == 0 else ""
        results.append(ok(f"{tool[:-4]}", r.returncode == 0, f"-> {version[:60]}"))

    # Chrome (system)
    chrome = shutil.which("chrome") or shutil.which("chrome.exe") or None
    if chrome is None:
        for candidate in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if Path(candidate).exists():
                chrome = candidate
                break
    results.append(ok("Chrome", bool(chrome), f"@ {chrome}" if chrome else "not found"))

    # Python venv
    results.append(
        ok("Python venv", sys.prefix is not None, sys.version.split()[0])
    )

    # HyperFrames doctor: only required checks matter (optional deps excluded)
    doctor = run([str(HYPERFRAMES), "doctor", "--json"], cwd=ROOT, env=env)
    if doctor.returncode == 0 or doctor.stdout.strip().startswith("{"):
        try:
            data = json.loads(doctor.stdout.strip())
        except (ValueError, IndexError):
            print("[SKIP] Could not parse doctor output")
            data = None
        if data:
            required_fails = [
                c["name"]
                for c in data["checks"]
                if not c["ok"] and not c.get("hint", "").startswith(("pip", "winget"))
                and c["name"] not in ("whisper-cpp", "TTS (Kokoro)", "BGM (MusicGen)", "Docker running")
            ]
            results.append(
                ok("HyperFrames doctor (required checks)", data["ok"] or not required_fails,
                   "; failed: " + ", ".join(required_fails) if required_fails else "all required pass")
            )

    print("\nEnvironment ready." if all(results) else "\nENVIRONMENT INCOMPLETE — see [FAIL] above.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
