# ElevenLabs ConvAI Ops — a Hermes Agent plugin

Operate [ElevenLabs ConvAI](https://elevenlabs.io/agents) voice agents from Hermes: inspect the
brain, change it safely, harden the prompt, and **measure** the agent with a real conversation
instead of guessing.

Built for the Hermes Agent Plugin Hackathon (Nov 2026).

## Why this exists

A voice agent has three knobs that decide whether callers hang up: the **LLM** behind it, the
**TTS model**, and the **prompt** (does it know today's date? does it ramble?). Today those are
dashboard clicks and vibes. This plugin turns them into tools with a diff, a backup and a number:

- every write is **dry-run by default** and returns the exact `old -> new` change
- every apply writes a **rollback backup** you can restore with one call
- every test returns **time-to-first-audio per turn**, the transcript, and the conversation id
- tool calls and credit cost are pulled from the **authoritative conversation record**, not the stream

## Tools

| Tool | What it does |
|---|---|
| `convai_agents_list` | list agents in the workspace |
| `convai_agent_inspect` | LLM, TTS model, voice, language, tool ids, prompt size, whether the prompt has date grounding and a brevity rule |
| `convai_agent_configure` | change `llm` / `tts_model_id` / `voice_id` — dry-run diff, backup, rollback |
| `convai_prompt_harden` | add `{{system__time_date}}` grounding + a brevity/no-spelling style rule; `action=restore` puts a backup back |
| `convai_voice_test` | run a text conversation over the ConvAI WebSocket, per-turn TTFA + spoken seconds + WAV/MP3, optional temporary model override that is restored afterwards |
| `convai_conversation` | authoritative transcript: turns, tool calls with parameters, termination reason, credits |

## Install

```bash
# 1. clone into your plugins directory
git clone https://github.com/<you>/hermes-elevenlabs-convai ~/.hermes/plugins/elevenlabs-convai

# 2. provide the key (profile secret or env)
hermes plugins enable elevenlabs-convai     # prompts for ELEVENLABS_API_KEY
# or: export ELEVENLABS_API_KEY=sk_...

# 3. verify
hermes plugins doctor elevenlabs-convai
```

Requirements: Hermes `>=0.21.6`, an ElevenLabs API key with ConvAI access, and (only for
`convai_voice_test`) the optional Python package `websockets` in the Hermes environment.

## Example session

```text
> convai_agent_inspect  agent_id=agent_...   → llm=claude-haiku-5-5, tts=eleven_v4_turbo, hardened=false
> convai_prompt_harden  agent_id=agent_...   → dry run: 7662 → 7929 chars, apply=false
> convai_prompt_harden  agent_id=agent_... apply=true → backup: ~/.hermes/cache/convai-backups/...
> convai_voice_test     agent_id=agent_... turns=["Ik wil vrijdag om acht uur een tafel voor vier."]
                        → TTFA 3010 ms, 11.6 s audio, conversation_id=conv_...
> convai_conversation   conversation_id=conv_... → tool calls, termination, credits
```

The loop this enables: **change one knob → measure → keep or revert.** The backup path returned by
every write is the revert.

## Safety and disclosure

- Reads and writes only your ElevenLabs account through `api.elevenlabs.io`; no other network calls,
  no telemetry, no local files besides backups and (opt-in) audio.
- `ELEVENLABS_API_KEY` is read through Hermes' secret scope; the plugin never logs or stores it.
- Writes are opt-in (`apply=true`) and backed up first; audio saving is opt-in (`save_audio_dir`).
- A conversation test spends real ElevenLabs credits on the account that owns the key.
- The WebSocket test needs `websockets`; on a core without it the other five tools still work and
  `convai_voice_test` returns a clear error naming the missing dependency.

## Development

```bash
hermes plugins validate . --install-deps   # the same check catalog CI runs
python3 tests/run_tests.py                 # unit tests, no network, no pytest needed
python3 smoke_test.py                      # live: needs ELEVENLABS_API_KEY + an agent id
```

## License

MIT
