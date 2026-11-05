#!/usr/bin/env python3
"""Render the demo MP4: a terminal-styled screencast of the plugin's real output.

Frames are drawn with PIL (no screen permissions, deterministic), narration comes from
demo/out/vo (ElevenLabs), captions are burned in so the video reads with sound off.

    python3 demo/render_video.py     -> demo/out/elevenlabs-convai-demo.mp4
"""
import json
import os
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
VO = OUT / "vo"
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
W, H, FPS = 1920, 1080, 30
GAP = 0.35          # silence between narration segments
TAIL = 0.9          # hold on the end card

BG, PANEL, EDGE = "#0b0e14", "#12161f", "#222a3a"
INK, DIM, MUTED = "#e6edf3", "#8b949e", "#5b6577"
CYAN, GREEN, AMBER = "#5ad1ff", "#59f7a3", "#ffd479"

MENLO = "/System/Library/Fonts/Menlo.ttc"
SANS = "/System/Library/Fonts/SFNS.ttf"
if not os.path.exists(SANS):
    SANS = "/System/Library/Fonts/Helvetica.ttc"

F_MONO = ImageFont.truetype(MENLO, 27)
F_MONO_S = ImageFont.truetype(MENLO, 24)
F_TITLE = ImageFont.truetype(SANS, 96)
F_SUB = ImageFont.truetype(SANS, 40)
F_SMALL = ImageFont.truetype(SANS, 28)
F_CAP = ImageFont.truetype(SANS, 36)
F_HEAD = ImageFont.truetype(SANS, 30)


def wrap(text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ── script: (narration id, list of (role, text)) ──────────────────────────────
# Terminal text is verbatim output from the real run (demo_runner.py), only the
# timings that vary per run are the ones that run produced.
SEGMENTS = [
    ("s1", [("title", "ElevenLabs ConvAI Ops"),
            ("subtitle", "a Hermes plugin · 6 tools"),
            ("foot", "dry run by default · backup + rollback on every write")]),
    ("s2", [("cmd", "python3 demo/demo_runner.py"),
            ("tool", '▸ convai_agent_inspect  {"agent_id": "agent_6001m6gh…"}'),
            ("dim", "  ← 736 ms"),
            ("kv", ("brain", "claude-haiku-5-5")),
            ("kv", ("voice", "yBtEjlHaWNu9xrYohjbA  (eleven_turbo_v2_5)")),
            ("kv", ("prompt", "7662 chars · date grounding: True · brevity rule: False"))]),
    ("s3", [("tool", '▸ convai_agent_configure  {"llm": "gpt-6-luna"}'),
            ("dim", "  ← 295 ms"),
            ("ok", "  dry run    claude-haiku-5-5 → gpt-6-luna   (nothing written)"),
            ("tool", '▸ convai_prompt_harden  {"agent_id": "agent_6001m6gh…"}'),
            ("dim", "  ← 300 ms"),
            ("ok", "  dry run    prompt 7662 → 7929 chars, changed=True   (apply=false)")]),
    ("s4", [("tool", '▸ convai_voice_test  {"turns": ["Hoi, ik wil vrijdag…", "…"]}'),
            ("dim", "  ← 14889 ms"),
            ("user", "user   Hoi, ik wil vrijdag graag een tafel voor vier personen om acht uur."),
            ("agent", "agent  Vrijdag is zes november. Klopt het dat je om acht uur 's avonds…"),
            ("ttfa", "       TTFA 3418 ms · 9.79 s audio"),
            ("user", "user   En kun je dat per e-mail bevestigen?"),
            ("agent", "agent  Nee, ik kan geen e-mails versturen en dit is alleen een demo…"),
            ("ttfa", "       TTFA 2297 ms · 17.08 s audio")]),
    ("s5", [("tool", '▸ convai_conversation  {"conversation_id": "conv_2101…", "wait_seconds": 20}'),
            ("dim", "  ← 3870 ms"),
            ("ok", "  transcript 4 turns · 0 tool calls · status done"),
            ("score", "● 2858 ms average time-to-first-audio (max 3418 ms)"),
            ("audio", "audio: demo/out/agent_6001m6gh…_conversation.mp3")]),
    ("s6", [("tool", "six tools, one toolset  elevenlabs_convai"),
            ("list", "convai_agents_list        convai_agent_inspect"),
            ("list", "convai_agent_configure    convai_prompt_harden"),
            ("list", "convai_voice_test         convai_conversation"),
            ("ok", "every write: dry run → diff → backup → apply → one-call rollback"),
            ("link", "github.com/NousResearch/hermes-agent/pull/149550")]),
    ("s7", [("title", "ElevenLabs ConvAI Ops"),
            ("subtitle", "github.com/c6zks4gssn-droid/hermes-elevenlabs-convai"),
            ("foot", "Hermes Plugin Hackathon · @NousResearch")]),
]


def decode_to_wav(mp3: Path, wav: Path) -> None:
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(mp3), "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_s16le", str(wav)], check=True)


def build_timeline(meta: dict) -> tuple[list[dict], float]:
    timeline, t = [], 0.0
    for seg_id, lines in SEGMENTS:
        entry = next(s for s in meta["segments"] if s["id"] == seg_id)
        dur = entry["seconds"]
        timeline.append({"id": seg_id, "start": t, "duration": dur, "lines": lines, "text": entry["text"]})
        t += dur + GAP
    return timeline, t + TAIL


def draw_frame(t: float, timeline: list[dict]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    seg = next((s for s in timeline if s["start"] <= t < s["start"] + s["duration"] + GAP), timeline[-1])
    p = min(1.0, max(0.0, (t - seg["start"]) / max(0.001, seg["duration"])))

    title_card = seg["lines"][0][0] == "title"
    if title_card:
        lines = seg["lines"]
        y = 360
        d.text((W // 2, y), lines[0][1], font=F_TITLE, fill=INK, anchor="mm")
        d.text((W // 2, y + 110), lines[1][1], font=F_SUB, fill=CYAN, anchor="mm")
        d.text((W // 2, y + 200), lines[2][1], font=F_SMALL, fill=MUTED, anchor="mm")
        d.line([(W // 2 - 90, y + 60), (W // 2 + 90, y + 60)], fill="#2a3446", width=2)
    else:
        d.rounded_rectangle([80, 80, W - 80, H - 80], radius=18, fill=PANEL, outline=EDGE, width=2)
        d.rounded_rectangle([80, 80, W - 80, 140], radius=18, fill="#161c27")
        for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            d.ellipse([(112 + i * 28, 100), (126 + i * 28, 114)], fill=col)
        d.text((220, 110), "hermes  ·  elevenlabs-convai", font=F_HEAD, fill=MUTED, anchor="lm")

        x, y, maxw = 130, 190, W - 300
        total_chars = sum(len(str(v)) if isinstance(v, tuple) else len(v) for _, v in seg["lines"])
        reveal = int(total_chars * min(1.0, p / 0.55))
        used = 0
        for role, value in seg["lines"]:
            text = value[1] if isinstance(value, tuple) else value
            if isinstance(value, tuple):
                text = f"{value[0]:<10} {value[1]}"
            shown = max(0, min(len(text), reveal - used))
            used += len(text)
            for part in wrap(text, F_MONO, maxw):
                chunk = part[:shown] if shown > 0 else ""
                if shown <= 0:
                    break
                shown -= len(part)
                color, font = INK, F_MONO
                if role == "cmd":
                    d.text((x, y), "$", font=F_MONO, fill=GREEN, anchor="la")
                    d.text((x + 24, y), chunk, font=F_MONO, fill=INK, anchor="la")
                elif role == "tool":
                    d.text((x, y), chunk, font=F_MONO, fill=CYAN, anchor="la")
                elif role == "dim":
                    d.text((x, y), chunk, font=F_MONO_S, fill=MUTED, anchor="la")
                elif role == "ok":
                    d.text((x, y), chunk, font=F_MONO, fill=GREEN, anchor="la")
                elif role == "ttfa":
                    d.text((x, y), chunk, font=F_MONO_S, fill=AMBER, anchor="la")
                elif role == "user":
                    d.text((x, y), chunk, font=F_MONO_S, fill=INK, anchor="la")
                elif role == "agent":
                    d.text((x, y), chunk, font=F_MONO_S, fill="#c3ceda", anchor="la")
                elif role == "score":
                    d.text((x, y), chunk, font=F_MONO, fill=GREEN, anchor="la")
                elif role == "audio":
                    d.text((x, y), chunk, font=F_MONO_S, fill=MUTED, anchor="la")
                elif role == "link":
                    d.text((x, y), chunk, font=F_MONO, fill=CYAN, anchor="la")
                else:
                    d.text((x, y), chunk, font=F_MONO, fill=color, anchor="la")
                y += 46

        # caption band: the narration text, chunked, for muted viewing
        chunks, cur = [], ""
        for word in seg["text"].split():
            trial = f"{cur} {word}".strip()
            if len(trial) <= 72:
                cur = trial
            else:
                chunks.append(cur)
                cur = word
        if cur:
            chunks.append(cur)
        idx = min(len(chunks) - 1, int(p * len(chunks)))
        d.rectangle([0, H - 168, W, H - 48], fill="#080a10")
        cap_lines = wrap(chunks[idx], F_CAP, W - 260)[:2]
        cy = H - 150
        for line in cap_lines:
            d.text((W // 2, cy), line, font=F_CAP, fill="#f2f5f9", anchor="ma")
            cy += 46

    # progress bar
    d.rectangle([0, H - 8, W, H], fill="#151a24")
    d.rectangle([0, H - 8, int(W * min(1.0, t / timeline[-1]["start"] + 0.0001)), H], fill=GREEN)
    return img


def main() -> None:
    meta = json.loads((VO / "segments.json").read_text())
    timeline, total = build_timeline(meta)
    print(f"video length {total:.2f}s · {len(timeline)} segments")

    # master audio: narration + gaps
    master = OUT / "narration.wav"
    with wave.open(str(master), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(44100)
        silence = b"\x00\x00\x00\x00" * int(44100 * GAP)
        for seg in timeline:
            wav = OUT / f"_tmp_{seg['id']}.wav"
            decode_to_wav(VO / f"{seg['id']}.mp3", wav)
            with wave.open(str(wav), "rb") as r:
                out.writeframes(r.readframes(r.getnframes()))
            out.writeframes(silence)
        out.writeframes(b"\x00\x00\x00\x00" * int(44100 * TAIL))

    frames = int(total * FPS) + 1
    video = OUT / "elevenlabs-convai-demo.mp4"
    proc = subprocess.Popen([FFMPEG, "-y", "-v", "error",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-i", str(master),
                             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)],
                            stdin=subprocess.PIPE)
    assert proc.stdin is not None
    _silence = b"\x00\x00\x00\x00"
    for i in range(frames):
        payload = draw_frame(i / FPS, timeline).tobytes()
        try:
            proc.stdin.write(payload)
        except (BrokenPipeError, ValueError):
            # ffmpeg got everything it needs (it stops one frame short of our count);
            # the last write racing its exit is not an error.
            break
        if i % 300 == 0:
            print(f"  frame {i}/{frames}")
    try:
        proc.stdin.close()
    except BrokenPipeError:
        pass
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ffmpeg exited {rc}")
    for tmp in OUT.glob("_tmp_*.wav"):
        tmp.unlink()
    print("wrote", video)


if __name__ == "__main__":
    main()
