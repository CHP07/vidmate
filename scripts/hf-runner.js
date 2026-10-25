#!/usr/bin/env node
/**
 * Scoped HyperFrames CLI launcher.
 *
 * Guarantees that every cache/history/state location HyperFrames writes to
 * lives inside the project directory instead of C:\ (user profile or TEMP):
 *
 *   .cache/hyperframes/history   project edit/render history blobs
 *                                (env: HYPERFRAMES_HISTORY_ROOT)
 *   .cache/hyperframes/extract   content-addressed frame cache during renders
 *                                (env: HYPERFRAMES_EXTRACT_CACHE_DIR;
 *                                default would be %TEMP%\hyperframes-extract-cache-*)
 *   .cache/hyperframes/fonts     Google Fonts cache
 *                                (env: HYPERFRAMES_FONT_CACHE_DIR)
 *   .cache/hyperframes/*         browser/TTS/optional-package caches, which have
 *                                no dedicated env var and resolve from homedir()
 *                                (.cache/hyperframes/chrome, /tts, /optional, ...)
 *   .hyperframes/                CLI config, install state, catalog artifacts
 *                                (~/.hyperframes by default)
 *
 * The homedir()-based paths are redirected by overriding HOME and USERPROFILE
 * for the CLI process only — pointing at .cache/user so that even children that
 * fabricate AppData-style paths under the profile land inside the gitignored
 * cache, never in the project root or on C:. This shell, your terminal and
 * other tools are unaffected. Usage: node scripts/hf-runner.js <cli args...>
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HF_CACHE = path.join(ROOT, ".cache", "hyperframes");

const env = {
  PATH: [
    path.join(ROOT, "tools", "ffmpeg"), // ffmpeg.exe / ffprobe.exe
    process.env.PATH,
  ].join(path.delimiter),
  HYPERFRAMES_HISTORY_ROOT: path.join(HF_CACHE, "history"),
  HYPERFRAMES_EXTRACT_CACHE_DIR: path.join(HF_CACHE, "extract"),
  HYPERFRAMES_FONT_CACHE_DIR: path.join(HF_CACHE, "fonts"),
  // Everything else HyperFrames or its children derive from the home
  // directory (config dir ~/.hyperframes, bundled-browser cache, optional
  // packages, TTS/parakeet models, AppData temps) lands inside .cache/user —
  // never in the project root, never on C:.
  HOME: path.join(ROOT, ".cache", "user"),
  USERPROFILE: path.join(ROOT, ".cache", "user"),
  APPDATA: path.join(ROOT, ".cache", "AppData", "Roaming"),
  LOCALAPPDATA: path.join(ROOT, ".cache", "AppData", "Local"),
  TEMP: path.join(ROOT, ".cache", "tmp"),
  TMP: path.join(ROOT, ".cache", "tmp"),
};

const CLI = path.join(ROOT, "node_modules", "hyperframes", "dist", "cli.js");
const result = spawnSync(process.execPath, [CLI, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: { ...process.env, ...env },
});
process.exit(result.status ?? 1);
