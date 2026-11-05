#!/usr/bin/env python3
"""Live smoke test: exercise every tool handler against the real ElevenLabs account.

Runs against the TEST agent unless AGENT is set. Uses a short two-turn scenario so the
credit cost stays tiny. Prints one line per tool.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/Users/clarenceetnel/Projects/hermes-elevenlabs-convai")

os.environ["ELEVENLABS_API_KEY"] = subprocess.run(
    ["security", "find-generic-password", "-s", "elevenlabs-api-key", "-w"],
    capture_output=True, text=True).stdout.strip()

# The plugin directory name contains a hyphen, so register it as a synthetic package
# before importing: relative imports inside the plugin then resolve normally.
import types  # noqa: E402

_PKG_DIR = "/Users/clarenceetnel/Projects/hermes-elevenlabs-convai"
_pkg = types.ModuleType("convai_plugin")
_pkg.__path__ = [_PKG_DIR]
sys.modules["convai_plugin"] = _pkg

from convai_plugin.tools import (  # noqa: E402
    _handle_agents_list, _handle_conversation, _handle_inspect,
    _handle_configure, _handle_prompt_harden, _handle_voice_test,
)

AGENT = os.environ.get("AGENT", "agent_6001m6ghzan8e7v8v2fxj1btgj5b")


def show(label, raw):
    data = json.loads(raw)
    if isinstance(data, dict) and data.get("error"):
        print(f"{label}: ERROR {data['error'][:300]}")
        return data
    print(f"{label}: ok")
    return data


agents = show("agents_list", _handle_agents_list({}))
print("   ", agents.get("count"), "agents")

insp = show("inspect", _handle_inspect({"agent_id": AGENT}))
print("    llm:", insp.get("llm"), "| tts:", insp.get("tts_model_id"), "| voice:", insp.get("voice_id"),
      "| hardened:", insp.get("hardened"))

dry = show("configure(dry)", _handle_configure({"agent_id": AGENT, "llm": "claude-haiku-5-5"}))
print("    diff:", dry.get("diff"))

hard_dry = show("prompt_harden(dry)", _handle_prompt_harden({"agent_id": AGENT}))
print("    changed:", hard_dry.get("changed"), "| chars:", hard_dry.get("current_chars"), "->", hard_dry.get("new_chars"))

audio_dir = "/Users/clarenceetnel/.hermes/profiles/glm/cache/scratch/convai-smoke"
run = show("voice_test", _handle_voice_test({
    "agent_id": AGENT,
    "turns": ["Hoi, ik wil vrijdag graag een tafel voor vier personen om acht uur."],
    "idle_seconds": 2.5,
    "save_audio_dir": audio_dir,
    "make_mp3": True,
}))
if isinstance(run, dict) and run.get("turns"):
    t = run["turns"][0]
    print("    ttfa:", t.get("ttfa_ms"), "ms | audio:", t.get("audio_seconds"), "s")
    print("    reply:", (t.get("agent") or "")[:160])
    print("    mp3:", run.get("mp3_path"))
    conv = run.get("conversation_id")
    if conv:
        det = show("conversation", _handle_conversation({"conversation_id": conv}))
        print("    tool_calls:", det.get("tool_call_count"), "| credits:", det.get("credits_used"))
