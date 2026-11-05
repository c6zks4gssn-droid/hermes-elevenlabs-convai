"""ElevenLabs ConvAI API client, prompt hardening and WebSocket conversation runner.

Stdlib only for HTTP (``urllib``); the WebSocket test needs the optional ``websockets``
package and reports a clear error when it is missing instead of failing the whole plugin.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE = "https://api.elevenlabs.io"
WS_BASE = "wss://api.elevenlabs.io/v1/convai/conversation"

DATE_BLOCK = (
    "CURRENT DATE: {{system__time_date}} (Europe/Amsterdam). "
    "Resolve every relative date the caller says ('aanstaande vrijdag', 'morgen', 'volgende week') "
    "to a real calendar date in the FUTURE based on this date before calling any availability or "
    "booking tool. Never invent or guess a year.\n\n"
)
STYLE_BLOCK = (
    "\n\nSTYLE: answer in at most two short sentences. One question per turn maximum. "
    "Never apologise about earlier turns, never repeat what you already said, "
    "never spell out a URL, e-mail address or phone number letter by letter, "
    "and always end with one concrete next step.\n"
)

# Model ids the ConvAI API accepts for the agent brain. Kept as a hint only: the live
# catalogue is read from the API (``model_ids``) and an invalid id is rejected by the API
# with the authoritative list in the error body.
KNOWN_LLMS = (
    "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5",
    "gpt-6-luna", "gpt-6-sol", "gpt-5.6-luna", "gpt-5.5",
    "gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash",
)


# ── credentials & transport ───────────────────────────────────────────────────
def api_key() -> str:
    """ElevenLabs API key: profile secret first, environment as fallback."""
    try:
        from agent.secret_scope import get_secret  # type: ignore

        value = get_secret("ELEVENLABS_API_KEY", "") or ""
    except Exception:  # pragma: no cover - outside Hermes
        value = ""
    return (value or os.environ.get("ELEVENLABS_API_KEY", "")).strip()


def _request(method: str, path: str, body: Optional[dict] = None, timeout: float = 45.0) -> Tuple[int, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("xi-api-key", key)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:600]}


def http(method: str, path: str, body: Optional[dict] = None) -> Any:
    """Call the API and raise a readable error on a non-2xx response."""
    status, payload = _request(method, path, body)
    if status >= 400:
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        raise RuntimeError(f"{method} {path} -> HTTP {status}: {json.dumps(detail)[:700]}")
    return payload


# ── agents ────────────────────────────────────────────────────────────────────
def agents_list(page_size: int = 30) -> List[Dict[str, Any]]:
    payload = http("GET", f"/v1/convai/agents?page_size={int(page_size)}")
    items = payload.get("agents", payload) if isinstance(payload, dict) else payload
    return [
        {"agent_id": a.get("agent_id"), "name": a.get("name"),
         "archived": a.get("archived"), "created_at": a.get("created_at")}
        for a in (items or [])
    ]


def agent_get(agent_id: str) -> Dict[str, Any]:
    return http("GET", f"/v1/convai/agents/{agent_id}")


def agent_patch(agent_id: str, conversation_config: Dict[str, Any]) -> Dict[str, Any]:
    return http("PATCH", f"/v1/convai/agents/{agent_id}", {"conversation_config": conversation_config})


def summarize_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, decision-relevant view of an agent's configuration."""
    cc = agent.get("conversation_config", {}) or {}
    prompt = ((cc.get("agent") or {}).get("prompt") or {})
    tts = cc.get("tts") or {}
    text = prompt.get("prompt") or ""
    return {
        "agent_id": agent.get("agent_id") or agent.get("agent_id"),
        "name": agent.get("name"),
        "llm": prompt.get("llm"),
        "temperature": prompt.get("temperature"),
        "language": (cc.get("agent") or {}).get("language"),
        "first_message": ((cc.get("agent") or {}).get("first_message") or "")[:160],
        "tts_model_id": tts.get("model_id"),
        "voice_id": tts.get("voice_id"),
        "tool_ids": prompt.get("tool_ids") or [],
        "prompt_chars": len(text),
        "prompt_has_date_variable": "{{system__time_date}}" in text or "{{system__time}}" in text,
        "prompt_has_style_block": "STYLE: answer in at most" in text,
        "has_phone_number": bool(agent.get("phone_number")),
    }


# ── catalogue ─────────────────────────────────────────────────────────────────
def model_ids() -> List[Dict[str, Any]]:
    payload = http("GET", "/v1/models")
    return [{"model_id": m.get("model_id"), "name": m.get("name"),
             "max_chars": m.get("maximum_text_length_per_request")} for m in payload]


def voices() -> List[Dict[str, Any]]:
    payload = http("GET", "/v1/voices")
    out = []
    for v in payload.get("voices", []):
        labels = v.get("labels") or {}
        out.append({"voice_id": v.get("voice_id"), "name": v.get("name"),
                    "language": labels.get("language") or labels.get("accent"),
                    "gender": labels.get("gender"), "use_case": labels.get("use_case")})
    return out


# ── prompt hardening ──────────────────────────────────────────────────────────
def prompt_is_hardened(prompt: str) -> bool:
    return "{{system__time_date}}" in prompt and "STYLE: answer in at most" in prompt


def harden_prompt(prompt: str) -> str:
    """Add the date-grounding and brevity blocks once; idempotent."""
    if prompt_is_hardened(prompt):
        return prompt
    body = prompt
    if "{{system__time_date}}" not in body:
        body = DATE_BLOCK + body.lstrip()
    if "STYLE: answer in at most" not in body:
        body = body.rstrip() + STYLE_BLOCK
    return body


def backup_dir() -> Path:
    try:
        from agent.secret_scope import get_secret  # type: ignore

        configured = get_secret("CONVAI_BACKUP_DIR", "") or ""
    except Exception:  # pragma: no cover
        configured = ""
    configured = configured or os.environ.get("CONVAI_BACKUP_DIR", "")
    if configured:
        path = Path(configured).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
        path = home / "cache" / "convai-backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_backup(agent_id: str, kind: str, payload: Dict[str, Any]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir() / f"{agent_id}_{kind}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


def load_backup(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


# ── WebSocket conversation test ───────────────────────────────────────────────
def _connect_kwargs(key: str) -> Dict[str, Any]:
    return {"additional_headers": {"xi-api-key": key}, "max_size": 32 * 1024 * 1024}


async def _run_conversation(agent_id: str, turns: List[str], idle_seconds: float,
                            cap_seconds: float, save_dir: Optional[str]) -> Dict[str, Any]:
    try:
        import websockets  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on the host env
        raise RuntimeError(
            "the optional dependency 'websockets' is not available in this Hermes environment; "
            "install it (pip install websockets) or use convai_agent_inspect/convai_conversation"
        ) from exc

    key = api_key()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    url = f"{WS_BASE}?agent_id={agent_id}"
    results: List[Dict[str, Any]] = []
    pcm_turns: List[bytes] = []
    conversation_id = None

    try:
        ws = await websockets.connect(url, **_connect_kwargs(key))
    except TypeError:  # websockets < 13 uses extra_headers
        ws = await websockets.connect(url, extra_headers={"xi-api-key": key}, max_size=32 * 1024 * 1024)

    async with ws:
        await ws.send(json.dumps({"type": "conversation_initiation_client_data"}))
        for index, text in enumerate(turns, 1):
            started = time.perf_counter()
            await ws.send(json.dumps({"type": "user_message", "text": text}))
            chunks: List[bytes] = []
            reply, ttfa, last_audio = None, None, None
            deadline = started + cap_seconds
            while time.perf_counter() < deadline:
                timeout = idle_seconds if last_audio else max(0.5, deadline - time.perf_counter())
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                message = json.loads(raw)
                kind = message.get("type")
                if kind == "conversation_initiation_metadata" and not conversation_id:
                    conversation_id = (message.get("conversation_initiation_metadata_event") or {}).get("conversation_id")
                elif kind == "audio":
                    chunk = base64.b64decode((message.get("audio_event") or {}).get("audio_base_64", ""))
                    chunks.append(chunk)
                    if ttfa is None:
                        ttfa = round((time.perf_counter() - started) * 1000)
                    last_audio = time.perf_counter()
                elif kind == "agent_response":
                    reply = (message.get("agent_response_event") or {}).get("agent_response")
                elif kind == "agent_response_correction":
                    corrected = (message.get("agent_response_correction_event") or {}).get("corrected_agent_response")
                    reply = corrected or reply
                elif kind == "ping" and last_audio and (time.perf_counter() - last_audio) > idle_seconds:
                    break
            pcm = b"".join(chunks)
            pcm_turns.append(pcm)
            results.append({"turn": index, "user": text, "agent": reply,
                            "ttfa_ms": ttfa, "audio_seconds": round(len(pcm) / 48000, 2),
                            "total_ms": round((time.perf_counter() - started) * 1000)})

    audio_path = None
    if save_dir and any(pcm_turns):
        target = Path(save_dir).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        audio_path = str(target / f"{agent_id}_conversation.wav")
        with wave.open(audio_path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            for pcm in pcm_turns:
                handle.writeframes(pcm)

    return {"conversation_id": conversation_id, "turns": results, "audio_path": audio_path}


def run_conversation(agent_id: str, turns: List[str], idle_seconds: float = 2.5,
                     cap_seconds: float = 40.0, save_dir: Optional[str] = None) -> Dict[str, Any]:
    """Run the scenario from a sync tool handler, even when a loop is already running."""
    coro = _run_conversation(agent_id, turns, idle_seconds, cap_seconds, save_dir)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def wav_to_mp3(wav_path: str) -> Optional[str]:
    """Best-effort mp3 next to the wav (needs ffmpeg); returns None when unavailable."""
    exe = None
    for candidate in (os.path.expanduser("~/.local/bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if os.path.exists(candidate):
            exe = candidate
            break
    if not exe:
        return None
    out = str(Path(wav_path).with_suffix(".mp3"))
    try:
        subprocess.run([exe, "-y", "-v", "error", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "4", out],
                       check=True, timeout=120)
        return out
    except Exception:  # pragma: no cover - ffmpeg is optional
        return None


# ── transcript ────────────────────────────────────────────────────────────────
def conversation_detail(conversation_id: str, wait_seconds: float = 0.0) -> Dict[str, Any]:
    """Fetch a conversation record.

    ElevenLabs keeps a fresh conversation in ``processing`` for a few seconds after the
    WebSocket closes; with ``wait_seconds`` this polls until the record is final so the
    transcript is not empty. Polling stops early on ``done``/``failed``/``error``.
    """
    data = http("GET", f"/v1/convai/conversations/{urllib.parse.quote(conversation_id)}")
    if wait_seconds and data.get("status") == "processing":
        deadline = time.time() + float(wait_seconds)
        while time.time() < deadline and data.get("status") == "processing":
            time.sleep(1.5)
            data = http("GET", f"/v1/convai/conversations/{urllib.parse.quote(conversation_id)}")
    metadata = data.get("metadata") or {}
    cost = metadata.get("cost") or {}
    transcript = []
    for turn in data.get("transcript") or []:
        calls = []
        for call in turn.get("tool_calls") or []:
            calls.append({"tool": call.get("tool_name"),
                          "params": call.get("params_as_json"),
                          "called": call.get("tool_has_been_called"),
                          "type": call.get("type")})
        transcript.append({"role": turn.get("role"),
                           "message": turn.get("message"),
                           "tool_calls": calls})
    return {
        "conversation_id": conversation_id,
        "status": data.get("status"),
        "duration_secs": metadata.get("call_duration_secs"),
        "termination_reason": metadata.get("termination_reason"),
        "credits_used": cost.get("credits_used") if isinstance(cost, dict) else None,
        "transcript": transcript,
    }
