"""Tool schemas and handlers for the ``elevenlabs_convai`` toolset."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import convai_client as core

TOOLSET = "elevenlabs_convai"


def tool_error(message: str) -> str:
    return json.dumps({"error": str(message)}, ensure_ascii=False)


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _available() -> bool:
    return bool(core.api_key())


# ── convai_agents_list ────────────────────────────────────────────────────────
AGENTS_LIST_SCHEMA = {
    "name": "convai_agents_list",
    "description": "List the ElevenLabs ConvAI agents in the workspace (agent_id, name, archived).",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _handle_agents_list(args: Dict[str, Any]) -> str:
    try:
        agents = core.agents_list()
        return _dump({"count": len(agents), "agents": agents})
    except Exception as exc:
        return tool_error(exc)


# ── convai_agent_inspect ──────────────────────────────────────────────────────
INSPECT_SCHEMA = {
    "name": "convai_agent_inspect",
    "description": (
        "Inspect one ConvAI agent: which LLM is its brain, which TTS model and voice it speaks with, "
        "language, attached tool ids, prompt size, and whether the prompt has date grounding and a "
        "brevity rule. Use this before changing anything."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ConvAI agent id (agent_...)"},
        },
        "required": ["agent_id"],
    },
}


def _handle_inspect(args: Dict[str, Any]) -> str:
    try:
        agent = core.agent_get(args["agent_id"])
        summary = core.summarize_agent(agent)
        summary["prompt_preview"] = (((agent.get("conversation_config") or {}).get("agent") or {})
                                     .get("prompt") or {}).get("prompt", "")[:400]
        summary["hardened"] = core.prompt_is_hardened(
            (((agent.get("conversation_config") or {}).get("agent") or {}).get("prompt") or {}).get("prompt") or ""
        )
        return _dump(summary)
    except Exception as exc:
        return tool_error(exc)


# ── convai_agent_configure ────────────────────────────────────────────────────
CONFIGURE_SCHEMA = {
    "name": "convai_agent_configure",
    "description": (
        "Change an agent's brain (LLM), TTS model and/or voice. Dry-run by default: it returns the "
        "exact old -> new diff and writes a rollback backup. Pass apply=true to actually patch the "
        "agent. Only the fields you name are touched."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ConvAI agent id (agent_...)"},
            "llm": {"type": "string", "description": "New brain, e.g. claude-haiku-5-5 or gpt-6-luna"},
            "tts_model_id": {"type": "string", "description": "New TTS model, e.g. eleven_turbo_v2_5"},
            "voice_id": {"type": "string", "description": "New voice id"},
            "apply": {"type": "boolean", "description": "Write the change (default false = dry run)"},
        },
        "required": ["agent_id"],
    },
}


def _handle_configure(args: Dict[str, Any]) -> str:
    try:
        agent_id = args["agent_id"]
        wanted: Dict[str, Any] = {}
        if args.get("llm"):
            wanted["llm"] = args["llm"]
        if args.get("tts_model_id"):
            wanted["tts_model_id"] = args["tts_model_id"]
        if args.get("voice_id"):
            wanted["voice_id"] = args["voice_id"]
        if not wanted:
            return tool_error("nothing to change: pass llm, tts_model_id and/or voice_id")

        agent = core.agent_get(agent_id)
        before = core.summarize_agent(agent)
        diff = {key: {"from": before.get(key), "to": value} for key, value in wanted.items()}

        payload: Dict[str, Any] = {"agent": {}}
        if "llm" in wanted:
            payload["agent"]["prompt"] = {"llm": wanted["llm"]}
        if "tts_model_id" in wanted or "voice_id" in wanted:
            tts = {}
            if "tts_model_id" in wanted:
                tts["model_id"] = wanted["tts_model_id"]
            if "voice_id" in wanted:
                tts["voice_id"] = wanted["voice_id"]
            payload["tts"] = tts

        if not args.get("apply"):
            return _dump({"agent_id": agent_id, "dry_run": True, "diff": diff, "payload": payload,
                          "hint": "call again with apply=true to write this; a backup is written first"})

        backup = core.write_backup(agent_id, "config", {"agent": before, "payload": payload})
        updated = core.agent_patch(agent_id, payload)
        after = core.summarize_agent(updated)
        return _dump({"agent_id": agent_id, "applied": True, "diff": diff, "backup": backup,
                      "after": {key: after.get(key) for key in wanted}})
    except Exception as exc:
        return tool_error(exc)


# ── convai_prompt_harden ──────────────────────────────────────────────────────
HARDEN_SCHEMA = {
    "name": "convai_prompt_harden",
    "description": (
        "Add date grounding ({{system__time_date}}) and a brevity/style rule to an agent prompt, or "
        "restore a previous version from a backup. Dry-run by default, idempotent, and every apply "
        "writes a full backup of the old prompt first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ConvAI agent id (agent_...)"},
            "action": {"type": "string", "enum": ["apply", "restore"],
                       "description": "apply = add the blocks, restore = put a backup back"},
            "backup_path": {"type": "string",
                            "description": "Backup file to restore (required when action=restore)"},
            "apply": {"type": "boolean", "description": "Write the change (default false = dry run)"},
        },
        "required": ["agent_id"],
    },
}


def _handle_prompt_harden(args: Dict[str, Any]) -> str:
    try:
        agent_id = args["agent_id"]
        action = (args.get("action") or "apply").lower()
        agent = core.agent_get(agent_id)
        current = ((((agent.get("conversation_config") or {}).get("agent") or {}).get("prompt") or {})
                   .get("prompt") or "")

        if action == "restore":
            path = args.get("backup_path")
            if not path:
                return tool_error("action=restore needs backup_path")
            saved = core.load_backup(path)
            target = saved.get("prompt") or (saved.get("agent") or {}).get("prompt")
            if not target:
                return tool_error(f"backup {path} has no prompt to restore")
            if not args.get("apply"):
                return _dump({"agent_id": agent_id, "dry_run": True, "action": "restore",
                              "backup_path": path, "restores_chars": len(target),
                              "current_chars": len(current)})
            core.agent_patch(agent_id, {"agent": {"prompt": {"prompt": target}}})
            return _dump({"agent_id": agent_id, "restored": True, "from": path, "chars": len(target)})

        new_prompt = core.harden_prompt(current)
        changed = new_prompt != current
        result = {"agent_id": agent_id, "dry_run": not args.get("apply"), "changed": changed,
                  "current_chars": len(current), "new_chars": len(new_prompt),
                  "already_hardened": not changed}
        if not args.get("apply"):
            result["hint"] = "call again with apply=true to write this"
            return _dump(result)

        if not changed:
            return _dump(result)
        backup = core.write_backup(agent_id, "prompt", {"agent_id": agent_id, "prompt": current})
        core.agent_patch(agent_id, {"agent": {"prompt": {"prompt": new_prompt}}})
        result.update({"applied": True, "backup": backup})
        return _dump(result)
    except Exception as exc:
        return tool_error(exc)


# ── convai_voice_test ─────────────────────────────────────────────────────────
VOICE_TEST_SCHEMA = {
    "name": "convai_voice_test",
    "description": (
        "Run a real text conversation against a ConvAI agent over the conversation WebSocket and "
        "measure time-to-first-audio per turn. Returns the transcript, per-turn TTFA, spoken seconds "
        "and the conversation id (use convai_conversation for tool calls and cost afterwards). "
        "Optional llm/tts_model_id/voice_id override the agent for this run only and are restored."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ConvAI agent id (agent_...)"},
            "turns": {"type": "array", "items": {"type": "string"},
                      "description": "User utterances, in order"},
            "idle_seconds": {"type": "number",
                             "description": "Silence after the last audio frame before the next turn (default 2.5)"},
            "save_audio_dir": {"type": "string",
                               "description": "Directory to write the conversation WAV into (optional)"},
            "make_mp3": {"type": "boolean", "description": "Also transcode the WAV to mp3 when ffmpeg exists"},
            "llm": {"type": "string", "description": "Temporarily switch the brain for this run"},
            "tts_model_id": {"type": "string", "description": "Temporarily switch the TTS model"},
            "voice_id": {"type": "string", "description": "Temporarily switch the voice"},
        },
        "required": ["agent_id", "turns"],
    },
}


def _handle_voice_test(args: Dict[str, Any]) -> str:
    try:
        agent_id = args["agent_id"]
        turns = [str(t) for t in (args.get("turns") or []) if str(t).strip()]
        if not turns:
            return tool_error("turns must contain at least one user utterance")

        override = {key: args[key] for key in ("llm", "tts_model_id", "voice_id") if args.get(key)}
        original = None
        if override:
            agent = core.agent_get(agent_id)
            original = core.summarize_agent(agent)
            payload: Dict[str, Any] = {"agent": {}}
            if "llm" in override:
                payload["agent"]["prompt"] = {"llm": override["llm"]}
            tts = {key: override[key] for key in ("tts_model_id", "voice_id") if key in override}
            if tts:
                payload["tts"] = tts
            if payload["agent"] or payload.get("tts"):
                core.agent_patch(agent_id, payload)

        try:
            run = core.run_conversation(
                agent_id, turns,
                idle_seconds=float(args.get("idle_seconds") or 2.5),
                save_dir=args.get("save_audio_dir"),
            )
        finally:
            if original:
                restore: Dict[str, Any] = {"agent": {}}
                if "llm" in override:
                    restore["agent"]["prompt"] = {"llm": original.get("llm")}
                tts_restore = {k: original.get(v) for k, v in
                               (("model_id", "tts_model_id"), ("voice_id", "voice_id")) if v in override}
                if tts_restore:
                    restore["tts"] = tts_restore
                if restore["agent"] or restore.get("tts"):
                    core.agent_patch(agent_id, restore)

        audio = run.get("audio_path")
        result = {"agent_id": agent_id, **(core.summarize_agent(core.agent_get(agent_id))),
                  "conversation_id": run.get("conversation_id"), "turns": run.get("turns"),
                  "audio_path": audio, "overrides_used": override}
        if audio and args.get("make_mp3"):
            result["mp3_path"] = core.wav_to_mp3(audio)
        ttfas = [t["ttfa_ms"] for t in run.get("turns") or [] if t.get("ttfa_ms")]
        if ttfas:
            result["ttfa_summary"] = {"avg_ms": round(sum(ttfas) / len(ttfas)), "max_ms": max(ttfas)}
        return _dump(result)
    except Exception as exc:
        return tool_error(exc)


# ── convai_conversation ───────────────────────────────────────────────────────
CONVERSATION_SCHEMA = {
    "name": "convai_conversation",
    "description": (
        "Fetch the authoritative transcript of a finished conversation: every turn, the tool calls "
        "with their parameters, the termination reason and the credits used. Use this instead of "
        "trusting the WebSocket stream when you need to prove what the agent did."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string", "description": "conv_... id from convai_voice_test"},
            "wait_seconds": {"type": "number",
                             "description": "Poll while the record is still 'processing' (default 0; 15 is a good value right after a test)"},
        },
        "required": ["conversation_id"],
    },
}


def _handle_conversation(args: Dict[str, Any]) -> str:
    try:
        detail = core.conversation_detail(args["conversation_id"], float(args.get("wait_seconds") or 0))
        detail["tool_call_count"] = sum(len(t["tool_calls"]) for t in detail["transcript"])
        return _dump(detail)
    except Exception as exc:
        return tool_error(exc)


TOOLS = (
    (AGENTS_LIST_SCHEMA, _handle_agents_list),
    (INSPECT_SCHEMA, _handle_inspect),
    (CONFIGURE_SCHEMA, _handle_configure),
    (HARDEN_SCHEMA, _handle_prompt_harden),
    (VOICE_TEST_SCHEMA, _handle_voice_test),
    (CONVERSATION_SCHEMA, _handle_conversation),
)


def register_tools(ctx) -> None:  # pragma: no cover - exercised by the plugin loader
    for schema, handler in TOOLS:
        ctx.register_tool(name=schema["name"], toolset=TOOLSET, schema=schema,
                          handler=handler, check_fn=_available, emoji="🎙️")
