"""ElevenLabs ConvAI Ops — operate ConvAI voice agents from Hermes Agent.

Tools (toolset ``elevenlabs_convai``):

``convai_agents_list``      list agents in the workspace
``convai_agent_inspect``    brain (LLM), TTS model, voice, tool wiring, prompt checks
``convai_agent_configure``  change llm / tts / voice — dry-run by default, backup + rollback
``convai_prompt_harden``    add date grounding + brevity rules to a prompt, restore later
``convai_voice_test``       run a real conversation over the ConvAI WebSocket, measure TTFA
``convai_conversation``     authoritative transcript, tool calls and credit cost

Auth: ``ELEVENLABS_API_KEY`` only; no credentials are stored by the plugin. Every write tool
takes ``apply`` (default false) and returns the exact diff it would make, plus a backup path so
``convai_prompt_harden``/``convai_agent_configure`` can be reverted.

Only public plugin surfaces are used: ``ctx.register_tool``.
"""

from __future__ import annotations

from .tools import TOOLS, TOOLSET, register_tools


def register(ctx) -> None:  # pragma: no cover - called by the Hermes plugin loader
    register_tools(ctx)


__all__ = ["register", "register_tools", "TOOLS", "TOOLSET"]
