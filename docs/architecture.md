# Fairy — architecture & internals

Everything here describes the **deployed** app unless a section says
*planned*. Reference: `fairy.py` (single-file PySide6 client, ~1000 lines).

## Shape of the app

`fairy.py` is a single frameless, transparent, always-on-top Qt widget
(`FramelessWindowHint | WindowStaysOnTopHint | Tool` +
`WA_TranslucentBackground`) on Wayland. A 33 ms `QTimer` drives a state
machine that selects a sprite pack per state, composites the pet at a size
interpolated between forms (72 → 110 → 148 px icon, up to a 300 px full-body
emerge), then paints the bubble, chip, and caret with QPainter.

States: `ONLINE / ATTENTIVE / LISTENING / THINKING / TALKING / GLITCH`.

## UI composition

- **Pet** — ring icon always visible. Hover grows her gently; a message or
  proactive quip can trigger the full-body emerge (rise → wake-stretch →
  expression), which sinks back after 25 s of disuse. Drag by grabbing the
  pet rect **including its center disc** (the ring's hole is grabbable).
- **Hover-fade chrome** — the status chip (`FAIRY // STATE`) and input line
  are hidden at rest. Each tick polls the cursor position against the pet/
  chip/input/bubble rects; a `self._ui` value lerps 0..1 and drives QPainter
  opacity (chip) and a `QGraphicsOpacityEffect` (input). Input stays up while
  it has keyboard focus or while dragging.
- **Bubble** — conversation-driven: shows for the last two transcript entries
  with typewriter caret; tailed to the pet, corner brackets, glitch jitter on
  GLITCH.
- **Position memory** — drag-release saves `fairy_position.json`; startup
  restores it clamped to the screen's available geometry.

## Brain adapters (`--brain`)

| brain | what it is |
|---|---|
| `strata` (default) | `ToolBrain`: local OpenAI-compatible server (Strata, `http://127.0.0.1:8080`) with **OpenAI function calling**. Model id auto-discovered from `/v1/models`. `persona.md` is the system prompt, plus a tool policy. `max_tokens` must stay ~1500: reasoning models burn the budget and small caps return empty content. |
| `stub` | canned persona replies, no LLM — proves the UI offline. |
| `discord` | legacy bridge: posts your line to a Discord channel and waits for the Hermes bot's reply. Needs `config.json` (gitignored; bot token + ids). |

`ToolBrain.reply()` runs an agent loop (max 4 tool rounds): assistant messages
containing `tool_calls` must be echoed back verbatim, followed by
`role: tool` results. Rolling memory keeps the last 10 user/assistant pairs;
every exchange is appended to `fairy_chat.jsonl` (gitignored).

### Tools

- `open_app(target)` — resolves via a PATH covering the Nix profile +
  `~/.local/bin`, with aliases (browser→firefox, terminal→alacritty,
  files→dolphin, notes→obsidian); URLs/files go through `xdg-open`.
- `close_app(name)` — `pkill -f -i`.
- `run_command(cmd)` — `bash -lc`, 120 s cap, output truncated; the persona
  policy tells her to confirm destructive commands with Master first.
- `open_hermes_session(note)` — launches
  `alacritty --title "FAIRY // HERMES SESSION" --working-directory DIR -e
  hermes chat --in DIR --no-restore-cwd -q SEED`, where SEED is the last 10
  exchanges framed as a handoff ("pick up where Fairy left off"). On a TTY,
  `hermes chat -q` seeds the transcript as the session's first turn, so full
  Hermes continues the exact conversation. DIR defaults to `~/vaults` when it
  exists, otherwise your home directory (`FAIRY_HERMES_DIR` overrides).

Brain failures render a deadpan GLITCH line instead of hanging.

## Behavior engine (presence)

A second 30 s `QTimer` evaluates, only when she is genuinely idle
(ONLINE state, not hovered, not dragging, no input focus, 45 s past the end
of any conversation, not mid-drift):

- **Idle quips** — first one 10–15 min after start, then every 10–20 min
  (probability roll each check). Lines come from a persona-voice pool
  (`IDLE_QUIPS`), shown as a bubble only.
- **Drift** — every 3–7 min she eases to a nearby spot: ±35–80 px horizontal,
  ±18 px vertical, animated 2 px per tick.
- **Move quips** — after YOU drag her she comments ~65% of the time, and two
  misses in a row are impossible (the second move always quips).

## Sprite pipeline

One authored base sprite → everything else, so both forms are one consistent
character:

1. `make_sprite.py` → `sprites/base/fairy.png` (strict cutout QA'd against
   reference panels; crown + glitch hair intact).
2. `make_full.py` → `sprites/full/*` — idle, stretch, smug, curious, talking,
   bust, surprised, recline: motion variations (breathe/tilt/bob/lean/pop) of
   the SAME base sprite.
3. `make_anim.py` → `sprites/anim/` (smooth) and `sprites/anim_pixel/`
   (chunky): ring-icon packs per state.
Re-run in that order after tuning amplitudes inside the scripts.

## QA

`test_behavior.py` exercises quip rendering, drift targeting, move-quip
guarantee, and hover gating offscreen
(`QT_QPA_PLATFORM=offscreen python3 test_behavior.py`). Visual QA is done by
`w.grab().save(...)` captures reviewed per change.

## Known limits (honest)

- Wayland window behavior is compositor-dependent (KWin); a real layer-shell
  integration is *planned*, not deployed.
- Tool brain quality follows the local model; with a small/quantized model,
  tool calls occasionally need a retry.
- `discord` brain needs a bot token and is not actively maintained.
