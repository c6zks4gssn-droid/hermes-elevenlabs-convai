#!/usr/bin/env python3
"""Deterministic demo runner for the <90 s recording.

Prints the plugin's six tools the way Hermes calls them, against a real ConvAI agent,
and finishes with the measurement table. Nothing is written to the agent: the only
mutation (prompt hardening) is a dry run, and the LLM/voice overrides are not used.

    python3 demo/demo_runner.py                # uses the test agent from DEMO_AGENT
    DEMO_AGENT=agent_xxx python3 demo/demo_runner.py
"""

import json
import os
import subprocess
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("ELEVENLABS_API_KEY", subprocess.run(
    ["security", "find-generic-password", "-s", "elevenlabs-api-key", "-w"],
    capture_output=True, text=True).stdout.strip())

_pkg = types.ModuleType("convai_plugin")
_pkg.__path__ = [ROOT]
sys.modules.setdefault("convai_plugin", _pkg)

from convai_plugin.tools import (  # noqa: E402
    _handle_conversation, _handle_inspect, _handle_configure,
    _handle_prompt_harden, _handle_voice_test,
)

AGENT = os.environ.get("DEMO_AGENT", "agent_6001m6ghzan8e7v8v2fxj1btgj5b")
TURNS = [
    "Hoi, ik wil vrijdag graag een tafel voor vier personen om acht uur.",
    "En kun je dat per e-mail bevestigen?",
]
OUT = os.path.join(ROOT, "demo", "out")

CLR = {"dim": "\033[2m", "bold": "\033[1m", "cyan": "\033[36m", "green": "\033[32m", "off": "\033[0m"}


def call(handler, tool, args):
    """Render a tool call the way an agent transcript shows it."""
    print(f"\n{CLR['cyan']}▸ {tool}{CLR['off']}{CLR['dim']}  {json.dumps(args, ensure_ascii=False)[:110]}{CLR['off']}")
    started = time.perf_counter()
    raw = handler(args if isinstance(args, dict) else {})
    elapsed = (time.perf_counter() - started) * 1000
    data = json.loads(raw)
    print(f"{CLR['dim']}  ← {elapsed:.0f} ms{CLR['off']}")
    return data


def line(text):
    print(f"  {text}")


def main() -> int:
    print(f"{CLR['bold']}ElevenLabs ConvAI Ops — plugin demo{CLR['off']}")
    print(f"{CLR['dim']}agent {AGENT}{CLR['off']}")

    info = call(_handle_inspect, "convai_agent_inspect", {"agent_id": AGENT})
    line(f"brain      {CLR['bold']}{info.get('llm')}{CLR['off']}")
    line(f"voice      {info.get('voice_id')}  ({info.get('tts_model_id')})")
    line(f"prompt     {info.get('prompt_chars')} chars · date grounding: {info.get('prompt_has_date_variable')}"
         f" · brevity rule: {info.get('prompt_has_style_block')}")

    dry = call(_handle_configure, "convai_agent_configure", {"agent_id": AGENT, "llm": "gpt-6-luna"})
    diff = dry.get("diff", {}).get("llm", {})
    line(f"dry run    {diff.get('from')} → {diff.get('to')}  (nothing written)")

    hard = call(_handle_prompt_harden, "convai_prompt_harden", {"agent_id": AGENT})
    line(f"dry run    prompt {hard.get('current_chars')} → {hard.get('new_chars')} chars, "
         f"changed={hard.get('changed')}  (apply=false)")

    run = call(_handle_voice_test, "convai_voice_test", {
        "agent_id": AGENT, "turns": TURNS, "idle_seconds": 2.5,
        "save_audio_dir": OUT, "make_mp3": True,
    })
    for turn in run.get("turns") or []:
        print(f"\n  {CLR['bold']}user{CLR['off']}   {turn['user']}")
        print(f"  {CLR['bold']}agent{CLR['off']}  {(turn.get('agent') or '')[:150]}")
        print(f"  {CLR['dim']}       TTFA {turn.get('ttfa_ms')} ms · {turn.get('audio_seconds')} s audio{CLR['off']}")

    conv = run.get("conversation_id")
    if conv:
        det = call(_handle_conversation, "convai_conversation", {"conversation_id": conv, "wait_seconds": 20})
        line(f"transcript {len(det.get('transcript') or [])} turns · "
             f"{det.get('tool_call_count')} tool calls · status {det.get('status')}")

    summary = run.get("ttfa_summary") or {}
    print(f"\n{CLR['green']}● {summary.get('avg_ms', '?')} ms average time-to-first-audio "
          f"(max {summary.get('max_ms', '?')} ms){CLR['off']}")
    print(f"{CLR['dim']}audio: {run.get('mp3_path') or run.get('audio_path')}{CLR['off']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
