# Demo — under 90 seconds

Record **screen only** (no webcam). 1920×1080 or a clean 1440×900 terminal. Large font
(≥ 16 pt), dark theme. The whole run takes ~20 s of real time, so the narration sets the pace,
not the tool.

Preparation, once:

```bash
cd ~/Projects/hermes-elevenlabs-convai
python3 demo/demo_runner.py --help >/dev/null 2>&1 || true   # warm the import cache
```

Have these windows ready: a terminal in the repo, and a browser tab on
`github.com/NousResearch/hermes-agent/pull/149550`.

---

## Shot list

| # | time | on screen | voice-over (EN) |
|---|---|---|---|
| 1 | 0:00–0:06 | terminal, cursor blinking | "A voice agent has three knobs that decide whether a caller hangs up: the model behind it, the voice, and the prompt." |
| 2 | 0:06–0:14 | `python3 demo/demo_runner.py` — inspect output appears | "This is a Hermes plugin that turns those knobs into tools. First, inspect: which brain, which voice, and does the prompt even know today's date?" |
| 3 | 0:14–0:26 | dry-run diff `claude-haiku-5-5 → gpt-6-luna`, then `prompt 7662 → 7929 chars` | "Every change is a dry run first — the exact diff, nothing written. Same for the prompt: it adds date grounding and a brevity rule, and it's idempotent." |
| 4 | 0:26–0:52 | the two turns, `TTFA 3418 ms` / `2297 ms` visible | "Then it actually talks to the agent over the WebSocket, in Dutch, and measures time-to-first-audio per turn: three-four seconds on the first turn, two-three on the second. That is the number a caller feels." |
| 5 | 0:52–1:02 | transcript line `4 turns · status done`, then `2858 ms average` | "The transcript and tool calls come from the authoritative conversation record, not from the stream — so the measurement is auditable. Apply writes a backup first; one call reverts it." |
| 6 | 1:02–1:14 | cut to the PR page (`pull/149550`) | "Six tools, dry-run by default, rollback on every write. Submitted to the Hermes plugin catalog — PR one-four-nine-five-five-zero." |
| 7 | 1:14–1:22 | end card: repo URL + `@NousResearch` | "Built for the Hermes plugin hackathon. Repo link below." |

Total ≈ 82 s. If you run long, cut shot 6 to four seconds and drop the PR number from the VO
(it is on screen and in the post).

## On-screen text (lower third, optional)

- 0:06 — `Hermes plugin · 6 tools`
- 0:14 — `dry run by default`
- 0:26 — `measured, not guessed`
- 0:52 — `backup + one-call rollback`

## Nederlandse versie (als je liever NL inspreekt)

1. "Een voice-agent heeft drie knoppen die bepalen of iemand ophangt: het model, de stem en de prompt."
2. "Dit is een Hermes-plugin die die knoppen tools maakt. Eerst inspecteren: welk brein, welke stem, en weet de prompt überhaupt welke datum het is?"
3. "Elke wijziging is eerst een dry-run met de exacte diff. Hetzelfde voor de prompt: datumgronding en een kortheidsregel, idempotent."
4. "Dan praat hij echt met de agent over de WebSocket, in het Nederlands, en meet per beurt de tijd tot het eerste audio: drie-vier seconden, dan twee-drie. Dat is wat een beller voelt."
5. "Transcript en tool-calls komen uit het gespreksrecord zelf, niet uit de stream. Toepassen maakt eerst een backup; één call draait het terug."
6. "Zes tools, dry-run als default, rollback bij elke schrijfactie. Ingediend voor de Hermes-plugincatalogus."
7. "Gebouwd voor de Hermes-pluginhackathon."

## Post copy (X)

> Voice agents have three knobs that decide if a caller hangs up: the brain, the voice, the prompt.
>
> So I built a Hermes plugin that turns them into tools — inspect, change with a dry run + backup, and *measure* time-to-first-audio on a real conversation.
>
> 6 tools, rollback on every write. Catalog PR: github.com/NousResearch/hermes-agent/pull/149550
> Code: github.com/c6zks4gssn-droid/hermes-elevenlabs-convai
>
> @NousResearch
>
> *(90 s demo below)*

Attach: the MP4. Post length is fine for X (280 chars? count: this is ~430 — trim the first line if
needed, or post as a thread with the video on the first tweet).

Shorter variant if you want one tweet:

> Built a Hermes plugin for @NousResearch: 6 tools to operate ElevenLabs ConvAI agents — inspect the brain, change it with dry-run + backup, and measure time-to-first-audio on a real conversation. 82 s demo. PR: github.com/NousResearch/hermes-agent/pull/149550

## Checklist before you post

- [ ] video ≤ 90 s, audio audible, no API key visible anywhere on screen
- [ ] terminal font big enough to read on a phone
- [ ] PR link typed correctly (`149550`)
- [ ] `@NousResearch` tagged
- [ ] Typeform filled with the X link **and** the PR link
