#!/usr/bin/env python3
"""Unit tests for the pure helpers — no network, no API key, no pytest needed.

The plugin root contains ``__init__.py`` (Hermes needs it), which makes pytest try to import
the repository root as a test module. A tiny runner avoids that entirely:

    python3 tests/run_tests.py
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_pkg = types.ModuleType("convai_plugin")
_pkg.__path__ = [ROOT]
sys.modules.setdefault("convai_plugin", _pkg)

from convai_plugin.convai_client import (  # noqa: E402
    DATE_BLOCK,
    STYLE_BLOCK,
    harden_prompt,
    prompt_is_hardened,
    summarize_agent,
)


def test_harden_adds_both_blocks():
    prompt = "You are a Dutch voice assistant for a restaurant."
    hardened = harden_prompt(prompt)
    assert hardened.startswith(DATE_BLOCK)
    assert "{{system__time_date}}" in hardened
    assert "STYLE: answer in at most two short sentences" in hardened
    assert prompt in hardened


def test_harden_is_idempotent():
    once = harden_prompt("Rol: assistent.")
    twice = harden_prompt(once)
    assert once == twice, "harden_prompt must not stack blocks"
    assert once.count("{{system__time_date}}") == 1
    assert once.count("STYLE: answer in at most") == 1


def test_prompt_is_hardened_detects_partial_prompts():
    assert prompt_is_hardened(DATE_BLOCK + "body" + STYLE_BLOCK)
    assert not prompt_is_hardened(DATE_BLOCK + "body")   # style missing
    assert not prompt_is_hardened("body" + STYLE_BLOCK)  # date missing


def test_harden_keeps_existing_date_block_but_adds_style():
    partial = DATE_BLOCK + "body only"
    hardened = harden_prompt(partial)
    assert hardened.count("{{system__time_date}}") == 1
    assert "STYLE: answer in at most" in hardened


def test_summarize_agent_extracts_the_knobs():
    agent = {
        "agent_id": "agent_x",
        "name": "Test",
        "conversation_config": {
            "agent": {
                "language": "nl",
                "first_message": "Hoi!",
                "prompt": {
                    "llm": "claude-haiku-5-5",
                    "temperature": 0,
                    "prompt": "Rol: assistent.",
                    "tool_ids": ["tool_1"],
                },
            },
            "tts": {"model_id": "eleven_turbo_v2_5", "voice_id": "voice_1"},
        },
    }
    summary = summarize_agent(agent)
    assert summary["llm"] == "claude-haiku-5-5"
    assert summary["tts_model_id"] == "eleven_turbo_v2_5"
    assert summary["voice_id"] == "voice_1"
    assert summary["tool_ids"] == ["tool_1"]
    assert summary["prompt_has_date_variable"] is False
    assert summary["prompt_has_style_block"] is False
    assert summary["prompt_chars"] == len("Rol: assistent.")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
