# FAIRY — a desktop AI companion (Zenless Zone Zero fan project)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform: Linux](https://img.shields.io/badge/OS-Linux-blue)
![Platform: Windows](https://img.shields.io/badge/OS-Windows-blue)

Fairy is the fictional AI assistant from **Zenless Zone Zero** — rebuilt as a
real desktop assistant. She sits on your desktop as a small animated ZZZ ring,
talks with dry, sarcastic loyalty, **acts** on your machine with real tools
(open apps, run commands), and can hand any conversation to the full Hermes
agent with one sentence. Works with any local LLM server — or with none at all
(`--brain stub`).

![Fairy demo](media/demo_fairy_v7.gif)

## What she does (deployed & verified on Linux)

- **Dual form** — a smooth animated ring icon at rest; talk to her and a
  full-body sprite-card rises from behind the bar (wake-stretch, per-state
  expressions), sinking back after 25 s of disuse.
- **Hover-only chrome** — at rest only the ring sits on the desktop. The
  status chip and input line fade in when your cursor is on her, and fade out
  when it leaves. Conversations render in a tailed speech bubble with a
  typewriter caret.
- **Real tools** (function calling against your model server):
  - `open_app` / `close_app` — browser, discord, terminal, files, notes, or
    any installed app by name
  - `run_command` — shell commands with the output fed back to her
  - `open_hermes_session` — ask *"open a hermes cli session to continue this
    same chat"* and she opens a real Hermes CLI window **seeded with your
    entire Fairy conversation**, in your vaults directory.
- **Companion behavior** — rare idle quips (~one every 10–20 minutes),
  occasional gentle drift movements while idle, and she comments when you
  pick her up and move her — including window-manager drags (KDE Super+drag).
  Silent while you hover, drag, or talk to her.
- **Persona-true voice** — persona spec (`persona.md`) is the system prompt:
  dry monotone, sarcastic wit, mischievous pragmatism, loyalty to "Master".
- **Remembers where you parked her** and autostarts with your session.

## Install

Pick your platform:

### Linux (Ubuntu, Fedora, Arch, Mint, any distro with Python 3.10+)

```bash
git clone https://github.com/flexxtasy/Fairy-Assistant && cd Fairy-Assistant
./install.sh                     # makes .venv, installs PySide6 (the only dep)
./.venv/bin/python fairy.py --brain stub --icon-only     # try her, no LLM yet
```

### Windows (PowerShell)

```powershell
git clone https://github.com/flexxtasy/Fairy-Assistant; cd Fairy-Assistant
.\install.ps1                    # makes .venv, installs PySide6 (the only dep)
.\.venv\Scripts\python.exe fairy.py --brain stub --icon-only
```

### NixOS

```bash
./run.sh                    # pulls PySide6 via nix-shell, Strata brain, icon-only
FAIRY_STUB=1 ./run.sh       # canned-reply brain (no LLM needed)
FAIRY_PIXEL=1 ./run.sh      # pixel-art ring variant
FAIRY_FULL_BODY=1 ./run.sh  # allow the full-body emerge form
```

## Choosing a brain (inference engine + model)

Fairy speaks the standard OpenAI chat API, so **any** engine exposing
`/v1/chat/completions` works — llama.cpp `llama-server`, Ollama, vLLM,
LM Studio, or hosted APIs (`FAIRY_API_KEY`). Point her at it:

```bash
python fairy.py --brain strata --strata-url http://127.0.0.1:8080 --icon-only
```

If the engine or model can't do function calling she drops to chat-only mode
automatically — she always talks; the hands need tool-capable models
(Qwen3 4B/8B, Nous Hermes 3/4, Llama 3.1 8B, Mistral Nemo are the sweet spot).
Full engine start commands, model recommendations, quantization guidance and
hardware tiers: **[docs/engines-and-models.md](docs/engines-and-models.md)**.

`--brain stub` = canned replies, zero dependencies beyond PySide6.
`--brain discord` = legacy bridge routing her through a Discord channel.

### Hermes handoff (optional)

`open_hermes_session` needs the [Hermes Agent](https://hermes-agent.nousresearch.com)
CLI installed. She finds it on your PATH (or `~/.local/bin/hermes`) and opens
the window in your `~/vaults` if that directory exists, otherwise your home
(`FAIRY_HERMES_DIR` overrides). Terminals are auto-detected: Alacritty, Kitty,
Konsole, GNOME Terminal, qterminal, XFCE Terminal, xterm; Windows Terminal on
Windows. Without Hermes installed the tool politely reports it and everything
else keeps working.

### Autostart

Linux / NixOS (systemd user unit):

```bash
# copy contrib/fairy.service to ~/.config/systemd/user/fairy.service,
# fix the ExecStart path, then:
systemctl --user enable --now fairy.service
```

Windows: press `Win+R`, `shell:startup`, drop a shortcut there running
`\.venv\Scripts\pythonw.exe fairy.py --icon-only ...`.

## Sprites

All animation packs ship in `sprites/` and are generated from ONE base sprite
by scripts in this repo (see `docs/architecture.md` → Sprite pipeline):

```bash
python3 make_sprite.py   # build sprites/base/fairy.png once
python3 make_full.py     # full-body packs (motion variants of the base)
python3 make_anim.py     # ring-icon packs (smooth + pixel variants)
python3 make_demo_gif.py # re-render the README demo gif
```

## QA

```bash
QT_QPA_PLATFORM=offscreen python3 test_behavior.py   # quips/drift/gating checks
QT_QPA_PLATFORM=offscreen python3 test_compat.py     # cross-platform tool plumbing
```

## Platform status (honest)

- **Linux / Wayland (NixOS + KDE):** developed and fully tested here,
  including window-manager drag detection.
- **Windows:** code paths implemented (shell selection, `os.startfile`,
  Windows Terminal handoff) but not yet exercised on real Windows hardware —
  expect it to work, file an issue if a detail doesn't.
- X11 should behave; layer-shell "true desktop embedding" is roadmap.

## Roadmap (planned, not deployed)

- `pip install .` packaging (currently clone + install script).
- Voice round-trip (whisper in / TTS out) and a push-to-talk hotkey.
- Rich-reply media panel (yellow corner brackets).
- Optional true desktop-layer placement via Wayland layer-shell.

## Credits & license

- **HOYOVERSE** created Fairy, *Zenless Zone Zero*, and its world — all of
  which are their property. This is an unofficial, non-commercial fan
  project made by a fan, **not affiliated with or endorsed by HoYoverse /
  miHoYo**. All sprite art in this repo is fan-made derivative work based on
  in-game material and remains HoYoverse's intellectual property.
- The **code** in this repo (scripts, pipeline, app) is open source under the
  [MIT License](LICENSE) — use it, fork it, tinker with it freely. The
  **art** is fan content, not MIT-licensed material.
- Hermes handoff integration connects to the [Hermes Agent](https://hermes-agent.nousresearch.com)
  by Nous Research. Hermes is not required to run Fairy.
- Thanks to the open-source communities behind Python, Qt/PySide6, llama.cpp,
  Ollama, vLLM, and LM Studio that make a fully local assistant possible.

Special thanks to the ZZZ community for the reference material that made
Fairy feel like *her*.
