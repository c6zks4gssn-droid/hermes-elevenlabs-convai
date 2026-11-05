#!/usr/bin/env python3
"""Render the demo voice-over with ElevenLabs and report each segment's duration."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

KEY = subprocess.run(["security", "find-generic-password", "-s", "elevenlabs-api-key", "-w"],
                     capture_output=True, text=True).stdout.strip()
OUT = Path(__file__).resolve().parent / "out" / "vo"
OUT.mkdir(parents=True, exist_ok=True)

SCRIPT = [
    ("s1", "A voice agent has three knobs that decide whether a caller hangs up: the model behind it, the voice, and the prompt."),
    ("s2", "This is a Hermes plugin that turns those knobs into tools. First, inspect: which brain, which voice, and does the prompt even know what day it is?"),
    ("s3", "Every change is a dry run first, with the exact diff and nothing written. Same for the prompt: it adds date grounding and a brevity rule, and running it twice changes nothing."),
    ("s4", "Then it actually talks to the agent over the WebSocket, in Dutch, and measures time to first audio per turn. Three point four seconds on the first turn, two point three on the second. That is the number a caller feels."),
    ("s5", "The transcript comes from the authoritative conversation record, not from the stream, so the measurement is auditable. Applying a change writes a backup first, and one call reverts it."),
    ("s6", "Six tools, dry run by default, rollback on every write. Submitted to the Hermes plugin catalog."),
    ("s7", "Built for the Hermes plugin hackathon."),
]


def voices():
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": KEY})
    data = json.load(urllib.request.urlopen(req, timeout=45))
    return data.get("voices", [])


def pick_voice():
    preferred = ("Brian", "Adam", "Daniel", "George", "Charlie", "River")
    candidates = []
    for v in voices():
        labels = v.get("labels") or {}
        if labels.get("language") not in ("en", "en-US", "en-GB", "english"):
            continue
        candidates.append(v)
    for name in preferred:
        for v in candidates:
            if v.get("name") == name:
                print("voice:", v["name"], v["voice_id"], v.get("labels"))
                return v["voice_id"]
    if candidates:
        print("voice (fallback):", candidates[0]["name"], candidates[0]["voice_id"])
        return candidates[0]["voice_id"]
    raise SystemExit("no English voice available")


def tts(voice_id: str, text: str, path: Path) -> None:
    body = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.25, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                                 data=body, headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    path.write_bytes(urllib.request.urlopen(req, timeout=180).read())


def duration(path: Path) -> float:
    out = subprocess.run(["~/.local/bin/ffprobe".replace("~", os.path.expanduser("~")), "-v", "error",
                          "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def main() -> None:
    voice = pick_voice()
    total = 0.0
    meta = []
    for name, text in SCRIPT:
        path = OUT / f"{name}.mp3"
        tts(voice, text, path)
        d = duration(path)
        total += d
        meta.append({"id": name, "file": str(path), "seconds": round(d, 3), "text": text})
        print(f"{name}: {d:5.2f}s  {len(text)} chars")
    (OUT / "segments.json").write_text(json.dumps({"voice_id": voice, "total": round(total, 3), "segments": meta}, indent=1))
    print(f"TOTAL narration: {total:.2f}s  (+1.2s tail = {total + 1.2:.2f}s video)")


if __name__ == "__main__":
    main()
