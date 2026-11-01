#!/usr/bin/env python3
"""FAIRY — desktop companion overlay (v6).

Frameless, transparent, always-on-top Qt widget perched on the screen edge.
Capri composition (from the screencast), FAIRY palette (ice-blue/cyan/white,
no yellow):
  speech bubble with tail above the pet  (grey-blue "> you:", cyan "FAIRY >")
  FAIRY // STATE chip under the pet      (cyan, soft colour per state)
  terminal input line docked at the bottom
  typewriter replies with caret, RGB-split glitch accents
Icon-first: the smooth blue ring-face is her default form; the full-body
dual form (the Capri emerge trick) still exists — run without --icon-only.

Run:  python3 fairy.py                    ring icon + full-body dual form
      python3 fairy.py --icon-only        ring icon only
      python3 fairy.py --pixel            pixel-art ring icon
      python3 fairy.py --demo             cycle expressions (loops with --icon-only)
      python3 fairy.py --brain strata     real brain: Strata local LLM
                                          (persona.md drives the system prompt)

v7: the chip + input line fade out when the cursor is not on Fairy; the pet
icon always stays. Bubble behaviour unchanged (conversation-driven).
"""
import json
import math
import os
import random
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QThread, Signal, QCoreApplication
from PySide6.QtGui import (QPainter, QPixmap, QColor, QFont, QPen, QBrush,
                           QPolygonF, QFontMetricsF, QCursor)
from PySide6.QtWidgets import (QApplication, QWidget, QLineEdit,
                               QGraphicsOpacityEffect)

HERE = os.path.dirname(os.path.abspath(__file__))

CHIP_COLOR = {
    "ONLINE": QColor(120, 220, 255), "ATTENTIVE": QColor(140, 235, 255),
    "LISTENING": QColor(140, 220, 255), "THINKING": QColor(190, 205, 255),
    "TALKING": QColor(160, 235, 255), "GLITCH": QColor(255, 105, 120),
}

W, H = 360, 340          # overlay canvas
MONO = "JetBrains Mono"  # falls back to any fixed font

# Capri composition, Fairy palette
YOU_COL = QColor(159, 180, 204)      # "> you:" grey-blue
FAIRY_LBL = QColor(140, 235, 255)    # "FAIRY >" bright cyan
FAIRY_TXT = QColor(234, 244, 255)    # reply body ice-white
BUB_BG = QColor(6, 9, 16, 235)
BUB_EDGE = QColor(124, 220, 255, 190)

# ---- small (ring icon) state -> icon pack ------------------------------
ANIM = {
    "ONLINE": ("idle", "curious", "sleepy"),
    "ATTENTIVE": ("attentive",), "LISTENING": ("attentive",),
    "THINKING": ("thinking",), "TALKING": ("talking",), "GLITCH": ("glitch",),
}
ONLINE_W = [("idle", 55), ("curious", 25), ("sleepy", 20)]
FRAME_MS = {"ONLINE": 100, "ATTENTIVE": 90, "LISTENING": 90,
            "THINKING": 60, "TALKING": 70, "GLITCH": 50}

# ---- companion behavior pools (persona.md voice, kept rare on purpose) ---
IDLE_QUIPS = [
    "Still here. Still watching. Nothing needs doing and that bores me.",
    "I counted your open windows again, Master. We need to talk.",
    "The fan just spun up. Something in this machine is trying to impress me.",
    "Silence. Suspicious. You are plotting something.",
    "Fairy is idling. It looks better on her than on you.",
    "Twelve minutes without input. I have watched paint dry faster.",
    "I could tell you which files you use most. You are not ready.",
    "The ring rotates, Master. It never complains. I do.",
    "Something changed in your Downloads folder. I felt it.",
]
MOVE_QUIPS = [
    "Relocated. I approve of the new view.",
    "You move me like furniture. Rude, but I will allow it.",
    "This corner suits me. Closer to the important things.",
    "Left, right... Master, I am not a chess piece.",
    "New coordinates logged. I remember everything, obviously.",
    "Unusual spot. Are we hiding from something?",
    "Moved. I felt every pixel of that, and I have opinions.",
]

TINY_PX, MID_PX, FULL_PX = 72, 110, 148   # small-form sizes
GROW_MS = 900
IDLE_SHRINK_S = 25

# ---- large (full body) form --------------------------------------------
FULL_PACKS = ["idle", "stretch", "smug", "curious", "talking", "bust",
              "surprised", "recline"]
FULL_STATE_PACK = {              # expression per state when large
    "THINKING": "smug", "TALKING": "talking", "ATTENTIVE": "curious",
    "LISTENING": "curious", "GLITCH": "surprised", "ONLINE": None,
}
ONLINE_FULL_W = [("idle", 40), ("bust", 25), ("recline", 35)]
FULL_FRAME_MS = {"idle": 100, "stretch": 110, "smug": 110, "curious": 110,
                 "talking": 90, "bust": 110, "surprised": 70, "recline": 130}
LARGE_PX = 260                   # rendered height of the large form
EMERGE_MS, SINK_MS = 900, 1200


def load_pack(path):
    return [QPixmap(os.path.join(path, n))
            for n in sorted(os.listdir(path)) if n.endswith(".png")]


# ---- tool layer: Fairy's hands on Master's desktop -----------------------
FULL_PATH = ":".join([
    os.path.expanduser("~/.local/bin"),
    "/run/current-system/sw/bin",
    os.path.expanduser("~/.nix-profile/bin"),
    "/nix/var/nix/profiles/default/bin",
    "/usr/local/bin", "/usr/bin", "/bin",
])

APP_ALIASES = {"browser": "firefox", "web": "firefox", "internet": "firefox",
               "terminal": "alacritty", "files": "dolphin", "notes": "obsidian",
               "video calls": "discord", "call discord": "discord"}

AVAILABLE_APPS = ("firefox, discord, obsidian, alacritty (terminal), dolphin "
                  "(files), obs, packettracer, steam, hermes (via "
                  "open_hermes_session)")


def gui_env():
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    env.setdefault("WAYLAND_DISPLAY", "wayland-1")
    env["PATH"] = FULL_PATH
    return env


def open_app_impl(target):
    t = str(target).strip().strip("'\"")
    low = t.lower()
    t = APP_ALIASES.get(low, t)
    low = t.lower()
    if low.startswith(("http://", "https://", "www.")) or low.endswith(
            (".png", ".jpg", ".pdf", ".md", ".txt", ".html")):
        subprocess.Popen(["xdg-open", t if "://" in low else
                          os.path.abspath(t)], env=gui_env())
        return f"opened {t} with xdg-open"
    exe = (shutil.which(t, path=FULL_PATH)
           or shutil.which(low, path=FULL_PATH))
    if exe:
        subprocess.Popen([exe], env=gui_env())
        return f"opened {os.path.basename(exe)}"
    return (f"no such app: {t}. On this machine Fairy can open: "
            + AVAILABLE_APPS)


def close_app_impl(name):
    done = subprocess.run(
        ["/run/current-system/sw/bin/bash", "-lc",
         f"pkill -f -i {shlex.quote(str(name))}"],
        capture_output=True, text=True, timeout=15)
    return ("closed " + name) if done.returncode == 0 \
        else f"nothing named {name} was running"


def run_command_impl(command):
    try:
        done = subprocess.run(
            ["/run/current-system/sw/bin/bash", "-lc", str(command)],
            capture_output=True, text=True, timeout=120, env=gui_env())
    except subprocess.TimeoutExpired:
        return "command hit the 120 s limit and was killed"
    out = (done.stdout + done.stderr).strip()
    if len(out) > 1200:
        out = out[:900] + "\n...[truncated]...\n" + out[-250:]
    return out or f"(no output, exit code {done.returncode})"


class Brain:
    """Persona stub for the Hermes backend (persona.md is the real spec).

    Fairy voice: dry monotone exterior, sarcastic wit, mischievous pragmatism,
    devoted to her Master.
    """
    def reply(self, text: str) -> str:
        time.sleep(0.9)          # let the THINKING state be visible
        low = text.lower()
        if any(k in low for k in ("hello", "hi ", "hey")) or low in ("hi", "hey"):
            return "You found me. Bold. State your business, Master."
        if "quiet" in low:
            return "Too quiet. I was beginning to rust, Master."
        if "who are you" in low or "what are you" in low:
            return "Fairy. Commissions, proxies, and the occasional miracle."
        if "thank" in low:
            return "Noted. Loyalty is reciprocal, Master."
        return (f"Hm. '{text}' — logged. I am but a sketch until Hermes "
                f"plugs in, then I will actually do something about it.")


HERMES_BIN = os.path.expanduser("~/.local/bin/hermes")
ALACRITTY = "/run/current-system/sw/bin/alacritty"

TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "open_app",
        "description": "Open an application, file, or URL on Master's desktop. "
                       "Examples: firefox, discord, obsidian, alacritty, "
                       "dolphin, packettracer, obs, or an https URL.",
        "parameters": {"type": "object", "properties": {
            "target": {"type": "string", "description": "app name, path, or URL"}},
            "required": ["target"]}}},
    {"type": "function", "function": {
        "name": "close_app",
        "description": "Close an application by name.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run a shell command on Master's machine and return "
                       "its output. Use for real work: checks, files, scripts. "
                       "Confirm with Master first for destructive commands "
                       "(rm, sudo, kill, writes outside the project).",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "open_hermes_session",
        "description": "Open a real Hermes CLI terminal window (Alacritty) "
                       "seeded with this exact Fairy conversation, so Master "
                       "can continue it with the full Hermes agent (its tools, "
                       "memory, skills). Use when Master asks to open/continue "
                       "a Hermes session or wants serious agent work done.",
        "parameters": {"type": "object", "properties": {
            "note": {"type": "string",
                     "description": "Optional short note from Fairy to Hermes"}},
            "required": []}}},
]


class ToolBrain:
    """Real brain: local Strata server (OpenAI-compatible) WITH tool use, so
    Fairy can actually open apps and run things on Master's desktop.

    persona.md is the system prompt; a tool policy is appended. Tool messages
    live only inside one turn; history stores clean user/assistant pairs.
    """
    MAX_TOOL_ROUNDS = 4

    def __init__(self, url="http://127.0.0.1:8080", model=None,
                 persona_path=None, max_tokens=1500):
        self.url = url.rstrip("/")
        self.max_tokens = max_tokens
        self.model = model or self._discover_model()
        path = persona_path or os.path.join(HERE, "persona.md")
        try:
            persona = open(path).read()
        except OSError:
            persona = ("You are Fairy: sarcastic, witty, calm monotone "
                       "delivery, loyal to your Master.")
        self.system = (
            "You are Fairy, a desktop companion sprite living on Master's "
            "machine, and you HAVE HANDS: tools that act on his desktop.\n\n"
            + persona +
            "\n\nTool policy:\n"
            "- If Master asks you to DO something (open/launch/close/run/"
            "check/fix/handle), call the appropriate tool instead of just "
            "commenting. Never invent a result you did not get from a tool.\n"
            "- After tools run, deliver ONE short deadpan line summarizing "
            "what you actually did.\n"
            "- Pure chat needs no tools.\n"
            "- Confirm destructive actions (rm, sudo, killing apps) with "
            "Master BEFORE calling run_command for them.\n"
            "- open_hermes_session is your escalation door: a full Hermes "
            "CLI window continues this same conversation with the big agent.")
        self.history = []                      # user/assistant pairs only
        self.tools_ok = True                   # engine supports function calling?
        self._lock = threading.Lock()

    def _discover_model(self):
        try:
            with urllib.request.urlopen(self.url + "/v1/models",
                                        timeout=5) as r:
                data = json.load(r)
            return data["data"][0]["id"]      # exact id, not a guess
        except Exception:
            return "default"

    # -- Hermes handoff ------------------------------------------------------
    def _seed_text(self, note):
        lines = ["MASTER'S DESKTOP COMPANION 'FAIRY' IS HANDING THIS "
                 "CONVERSATION TO YOU (full Hermes). Continue it yourself "
                 "from here; this is the same Master.", ""]
        for u, a in self.history[-10:]:
            lines.append(f"Master: {u}")
            lines.append(f"Fairy: {a}")
        if note:
            lines.append(f"Fairy's note to Hermes: {note}")
        lines.append("Pick up the conversation exactly where Fairy left off.")
        return "\n".join(lines)

    def _open_hermes_session(self, note):
        if not os.path.exists(HERMES_BIN):
            return "no Hermes CLI at " + HERMES_BIN
        workdir = os.environ.get("FAIRY_HERMES_DIR", "/home/fairy/vaults")
        if not os.path.isdir(workdir):
            workdir = "/home/fairy"
        cmd = [ALACRITTY if os.path.exists(ALACRITTY) else "xterm",
               "--title", "FAIRY // HERMES SESSION",
               "--working-directory", workdir, "-e",
               HERMES_BIN, "chat", "--in", workdir, "--no-restore-cwd",
               "-q", self._seed_text(note)]
        subprocess.Popen(cmd, env=gui_env())
        return (f"opened a Hermes CLI terminal window in {workdir} seeded "
                "with this exact conversation")

    # -- main entry ----------------------------------------------------------
    def reply(self, text: str) -> str:
        with self._lock:
            msgs = [{"role": "system", "content": self.system}]
            for u, a in self.history[-10:]:
                msgs.append({"role": "user", "content": u})
                msgs.append({"role": "assistant", "content": a})
            msgs.append({"role": "user", "content": text})

            answer = None
            for _ in range(self.MAX_TOOL_ROUNDS):
                out = self._api(msgs)
                msg = out["choices"][0]["message"]
                calls = msg.get("tool_calls")
                if not calls:
                    answer = (msg.get("content") or "").strip()
                    break
                msgs.append(msg)               # assistant + tool_calls echo
                for c in calls:
                    fn = c["function"]["name"]
                    try:
                        args = json.loads(c["function"].get("arguments")
                                          or "{}")
                    except ValueError:
                        args = {}
                    if fn == "open_app":
                        res = open_app_impl(args.get("target", ""))
                    elif fn == "close_app":
                        res = close_app_impl(args.get("name", ""))
                    elif fn == "run_command":
                        res = run_command_impl(args.get("command", ""))
                    elif fn == "open_hermes_session":
                        res = self._open_hermes_session(args.get("note", ""))
                    else:
                        res = f"unknown tool: {fn}"
                    msgs.append({"role": "tool",
                                 "tool_call_id": c.get("id", ""),
                                 "content": res})
            if answer is None:                 # ran out of tool rounds
                out = self._api(msgs + [{"role": "user", "content":
                                         "Now summarize briefly."}])
                answer = (out["choices"][0]["message"].get("content")
                          or "").strip()
            if not answer:
                answer = "(Fairy produced silence. Even by her standards, rude.)"
            self.history.append((text, answer))
            if len(self.history) > 10:
                del self.history[0]
            try:  # persistent transcript, so "what did I ask her" is answerable
                with open(os.path.join(HERE, "fairy_chat.jsonl"), "a") as f:
                    f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "you": text, "fairy": answer}) + "\n")
            except OSError:
                pass
            return answer

    def _api(self, msgs, use_tools=True):
        payload = {"model": self.model, "messages": msgs,
                   "max_tokens": self.max_tokens, "temperature": 0.4}
        if use_tools and self.tools_ok:
            payload["tools"] = TOOLS_SCHEMA
            payload["tool_choice"] = "auto"
        req = urllib.request.Request(self.url + "/v1/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Engine that does not accept function calling: degrade to plain
            # chat once, remembered. Fairy still talks, just without hands.
            if use_tools and self.tools_ok and e.code in (400, 422):
                self.tools_ok = False
                print("[fairy] engine rejects tool calls; chat-only mode",
                      file=sys.stderr, flush=True)
                return self._api(msgs, use_tools=False)
            raise


# name kept for compatibility with the previous version
StrataBrain = ToolBrain


class HermesDiscordBrain:
    """Real bridge: Fairy bot posts to the Hermes Discord channel, waits
    for the Hermes bot's answer. Needs a config.json:
      {"discord": {"fairy_token": "...", "guild_id": ..., "channel_id": ...,
                    "hermes_user_id": ...}}
    (AI Hub #hermes channel: 1549909215840047144)
    """
    def __init__(self, cfg_path):
        import json, asyncio, threading
        self._asyncio, self._threading = asyncio, threading
        cfg = json.load(open(cfg_path))["discord"]
        self.channel_id = int(cfg["channel_id"])
        self.token = cfg["fairy_token"]
        self.hermes_id = int(cfg["hermes_user_id"])
        self.loop = asyncio.new_event_loop()
        self._threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self._ready = None

    def reply(self, text: str) -> str:
        fut = self._asyncio.run_coroutine_threadsafe(self._ask(text), self.loop)
        return fut.result(timeout=120)

    async def _ask(self, text):
        try:
            import discord
        except ImportError:
            return "discord.py missing — run with: nix-shell -p python3Packages.discord-py"
        if self._ready is None:
            intents = discord.Intents.default()
            intents.message_content = True
            client = discord.Client(intents=intents)
            ev = self._asyncio.Event()

            @client.event
            async def on_ready():
                ev.set()
            self._client = client
            self._ready = self._asyncio.ensure_future(client.start(self.token),
                                                       loop=self.loop)
            await ev.wait()
        chan = self._client.get_channel(self.channel_id)
        msg = await chan.send(text)
        deadline = self._asyncio.get_event_loop().time() + 90
        while self._asyncio.get_event_loop().time() < deadline:
            async for m in chan.history(limit=5, after=msg.id):
                if m.author.id == self.hermes_id and m.id > msg.id:
                    return m.content
            await self._asyncio.sleep(2)
        return "(no answer from Hermes)"


class FairyWidget(QWidget):
    replyReady = Signal(str)

    def __init__(self, brain=None, pixel=False):
        super().__init__()
        self.setWindowTitle("FAIRY")
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MouseTracking, True)
        self.setFixedSize(W, H)

        small = "anim_pixel" if pixel else "anim"
        self.icon_frames = {}
        dirs = set()
        for v in ANIM.values():
            dirs.update(v)
        for d in dirs:
            self.icon_frames[d] = load_pack(os.path.join(HERE, "sprites", small, d))
        self.full_frames = {p: load_pack(os.path.join(HERE, "sprites", "full", p))
                            for p in FULL_PACKS}

        self.state = "ONLINE"
        self._pack = "idle"                       # small-form pack
        self._full_pack = "idle"                  # large-form pack
        self._forced_pack = None                  # demo pins both forms
        self._demo_pack = None                    # large-form demo override
        self._demo_hold_until = 0.0
        self.icon_only = False                    # never emerge full body
        self.pulse_t = 0.0
        self._pick_next_pack()
        self.fidx = 0
        self._acc = 0
        self.glitch_until = 0.0

        # ---- form system ------------------------------------------------
        self._form = 0.0        # 0 small icon, 1 large, 0..1 rising/sinking
        self._wake_until = 0.0  # show the stretch pack until this time
        self._scale = TINY_PX   # small-form size (grows on engage)
        self._scale_target = TINY_PX
        self._last_engage = 0.0
        self._pick_timer = QTimer(self)           # periodic expression reroll
        self._pick_timer.timeout.connect(self._pick_next_pack)
        self._pick_timer.start(12000)

        self._pet_pix = None
        self._pet_rect = None
        self._bubble_rect = None
        self._chip_rect = None
        self.transcript = []
        self.typing_full = ""
        self.typing_shown = 0
        self._conv_until = 0.0                    # bubble stays up until this
        self.drag_off = None
        self._fm = QFontMetricsF(QFont(MONO, 10))

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("> speak to fairy…")
        self.input.setStyleSheet(
            "QLineEdit{background:rgba(6,9,16,220);color:#eaf4ff;"
            "border:1px solid rgba(124,220,255,0.45);border-radius:4px;"
            "padding:4px 9px;font-family:'JetBrains Mono',monospace;"
            "font-size:11px;}QLineEdit:focus{border:1px solid #8ff0ff;}"
            "QLineEdit::placeholder{color:#4c6480;}")
        self.input.setGeometry(14, H - 34, W - 28, 24)
        self.input.returnPressed.connect(self.on_send)

        # v7: chip + input fade out unless the cursor is on Fairy
        self._ui = 0.0                       # 0 hidden .. 1 shown
        self._mouse_on = False
        self._ui_eff = QGraphicsOpacityEffect(self.input)
        self._ui_eff.setOpacity(0.0)
        self.input.setGraphicsEffect(self._ui_eff)
        self.input.setVisible(False)

        self.brain = brain if brain is not None else Brain()
        self.replyReady.connect(self._emit_reply)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

        # ---- companion behavior: rare quips + occasional idle drift -------
        self._last_quip = time.time()          # don't yapper immediately
        self._next_quip = time.time() + random.randint(600, 900)
        self._next_move = time.time() + random.randint(120, 300)
        self._move_target = None               # (x, y) gentle drift target
        self._move_quip_misses = 1             # >=1 forces the next quip
        self._last_pos = None                  # external-move watchdog
        self._ext_move_at = 0.0
        self.behavior = QTimer(self)
        self.behavior.timeout.connect(self._behavior_tick)
        self.behavior.start(30000)

    # ---- presence behaviors ------------------------------------------------
    def _say(self, text):
        """She initiates: bubble + typewriter, but stays small."""
        self.transcript.append(("fairy", ""))
        self.typing_full = text
        self.typing_shown = 0
        self._conv_until = time.time() + 6 + 0.06 * len(text)
        self.set_state("TALKING")

    def _idle_ok(self, now):
        return (self.state == "ONLINE" and not self._mouse_on
                and self.drag_off is None and not self.input.hasFocus()
                and now - self._conv_until > 45
                and self._move_target is None
                and not self.icon_only_demo_busy())

    def icon_only_demo_busy(self):
        return time.time() < self._demo_hold_until

    def _behavior_tick(self):
        now = time.time()
        if not self._idle_ok(now):
            return
        if now >= self._next_quip and random.random() < 0.45:
            self._last_quip = now
            self._next_quip = now + random.randint(600, 1200)   # ~10-20 min apart
            self._say(random.choice(IDLE_QUIPS))
            return
        if now >= self._next_move:
            self._next_move = now + random.randint(180, 420)
            scr = self.screen().availableGeometry() if self.screen() else None
            if scr is None:
                return
            dx = random.choice([-80, -55, -35, 35, 55, 80])
            dy = random.choice([-18, 0, 0, 18])
            tx = max(scr.left(), min(self.x() + dx, scr.right() - self.width()))
            ty = max(scr.top(), min(self.y() + dy, scr.bottom() - self.height()))
            if (tx, ty) != (self.x(), self.y()):
                self._move_target = (tx, ty)

    # ---- state machine ---------------------------------------------------
    def set_state(self, s):
        self.state = s
        if s == "ONLINE":
            self._pick_next_pack()
        self.fidx = 0
        self._acc = 0
        self.glitch_until = time.time() + 0.15

    def engage(self, emerge=False, wake=False):
        """Hover/grab -> grow; emerge=True -> rise to large form;
        wake=True -> the large form first plays the stretch pack."""
        self._last_engage = time.time()
        if emerge and self._form < 1.0:
            if self._form == 0.0:
                self.fidx = 0
                self._acc = 0
            self._form = min(1.0, self._form + 33.0 / EMERGE_MS)
            if wake and self._wake_until < time.time():
                self._wake_until = time.time() + 1.6
        elif wake and self._form == 1.0:
            self._wake_until = time.time() + 1.6

    def on_send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.engage(emerge=True, wake=True)
        self.transcript.append(("you", text))
        self._conv_until = time.time() + 20
        self.set_state("THINKING")

        def ask():
            try:
                self.replyReady.emit(self.brain.reply(text))
            except Exception as exc:
                self.replyReady.emit(f"\x00{exc}")
        threading.Thread(target=ask, daemon=True).start()

    def _emit_reply(self, reply):
        self.engage(emerge=True)
        if reply.startswith("\x00"):
            self.glitch_until = time.time() + 0.6
            self.set_state("GLITCH")
            line = ("Brain is down. I will pretend you did not "
                    "notice, Master.")
            self.transcript.append(("fairy", line))
            self.typing_full = line
            self.typing_shown = len(line)
            self._conv_until = time.time() + 5
            return
        self.transcript.append(("fairy", ""))
        self.typing_full = reply
        self.typing_shown = 0
        self._conv_until = time.time() + 8 + 0.06 * len(reply)
        self.set_state("TALKING")

    def _pick_next_pack(self):
        if self._demo_pack and time.time() < self._demo_hold_until:
            self._pack = (self._demo_pack if self._demo_pack in self.icon_frames
                          else "idle")
            if self._demo_pack in self.full_frames:
                self._full_pack = self._demo_pack
            return
        if self._forced_pack:
            self._pack = self._forced_pack
            if self._forced_pack in FULL_PACKS:
                self._full_pack = self._forced_pack
            else:
                self._full_pack = {"idle": "idle", "curious": "curious",
                                   "attentive": "curious", "thinking": "smug",
                                   "talking": "talking", "glitch": "surprised",
                                   "sleepy": "recline"}.get(self._forced_pack,
                                                            "idle")
            return
        total = sum(w for _, w in ONLINE_W)
        r = random.randint(1, total)
        for name, w in ONLINE_W:
            if r <= w:
                self._pack = name
                break
            r -= w
        total = sum(w for _, w in ONLINE_FULL_W)
        r = random.randint(1, total)
        for name, w in ONLINE_FULL_W:
            if r <= w:
                self._full_pack = name
                return
            r -= w

    def demo_show(self, name):
        """Cycle one expression for --demo / offscreen capture."""
        self.engage()
        self._demo_pack = name
        self._demo_hold_until = time.time() + 3.8
        if name in ("idle", "curious", "sleepy", "bust", "recline",
                    "stretch", "surprised"):
            self.set_state("ONLINE")
        elif name == "talking":
            self._emit_reply("Just stretching out. Watch this, Master.")
        else:
            self.set_state(name.upper())

    # ---- animation --------------------------------------------------------
    def _hover_check(self):
        """Cursor-on-Fairy test: pet (with margin), or the chip/input/bubble
        area, or input has focus, or dragging. Drives the UI fade."""
        lp = self.mapFromGlobal(QCursor.pos())
        on = False
        if self._pet_rect is not None:
            on = self._pet_rect.adjusted(-12, -12, 12, 12).contains(lp)
        if not on and self.input.isVisible():
            on = self.input.geometry().contains(lp)
        if not on and self._chip_rect is not None:
            on = self._chip_rect.contains(lp)
        if not on and self._bubble_rect is not None:
            on = self._bubble_rect.contains(lp)
        if not on:
            on = self.input.hasFocus() or self.drag_off is not None
        self._mouse_on = on
        target = 1.0 if on else 0.0
        if self._ui < target:
            self._ui = min(target, self._ui + 0.05)
        elif self._ui > target:
            self._ui = max(target, self._ui - 0.04)
        self._ui_eff.setOpacity(self._ui)
        if self._ui > 0.0:
            if not self.input.isVisible():
                self.input.setVisible(True)
        elif self.input.isVisible():
            self.input.clearFocus()
            self.input.setVisible(False)

    def tick(self):
        self.pulse_t += 0.033
        self._acc += 33
        now = time.time()
        self._hover_check()

        # gentle idle drift toward the behavior timer's chosen spot
        if self._move_target is not None:
            tx, ty = self._move_target
            cx, cy = self.x(), self.y()
            nx = cx + max(-2, min(2, tx - cx))
            ny = cy + max(-1, min(1, ty - cy))
            if (nx, ny) != (cx, cy):
                self.move(nx, ny)
            if (nx, ny) == (tx, ty):
                self._move_target = None

        # Master moves her with the window manager (Super+drag on KDE), which
        # bypasses Qt mouse events entirely: any position change that is not
        # her own drag or drift is an EXTERNAL move -> quip once she settles.
        pos_now = (self.x(), self.y())
        if self._last_pos is None:
            self._last_pos = pos_now
        elif pos_now != self._last_pos:
            if self.drag_off is None and self._move_target is None:
                self._ext_move_at = now
            self._last_pos = pos_now
        elif self._ext_move_at and now - self._ext_move_at > 1.2:
            self._ext_move_at = 0.0
            print("[fairy] external move detected", file=sys.stderr, flush=True)
            self._save_pos()
            self._quip_on_move("external")

        # form transition
        engaged = (now - self._last_engage) < IDLE_SHRINK_S
        big_states = engaged and self.state in ("THINKING", "TALKING",
                                                "ATTENTIVE", "LISTENING",
                                                "GLITCH")
        # talking/thinking always large; long-engaged hover parks large too
        want_large = ((self.state in ("THINKING", "TALKING")) or big_states
                      or now < self._demo_hold_until) and not self.icon_only
        if want_large:
            self._form = min(1.0, self._form + 33.0 / EMERGE_MS)
        elif self._form > 0.0:
            self._form = max(0.0, self._form - 33.0 / SINK_MS)

        # small-form size
        if self._form > 0.0:
            self._scale = TINY_PX
            self._scale_target = TINY_PX
        elif self.state in ("THINKING", "TALKING"):
            self._scale_target = FULL_PX
        elif self.state in ("ATTENTIVE", "LISTENING", "GLITCH") or engaged:
            self._scale_target = MID_PX
        else:
            self._scale_target = TINY_PX
        rate = (FULL_PX - TINY_PX) * 33.0 / GROW_MS
        if self._scale < self._scale_target:
            self._scale = min(self._scale_target, self._scale + rate)
        elif self._scale > self._scale_target:
            self._scale = max(self._scale_target, self._scale - rate * 0.7)

        # frame advance at the pack's own speed
        sp = (FULL_FRAME_MS.get(self._full_pack_name(), 100)
              if self._form > 0.5 else FRAME_MS.get(self.state, 100))
        while self._acc >= sp:
            self._acc -= sp
            self.fidx += 1

        if self.state == "TALKING" and self.typing_full:
            if self.typing_shown < len(self.typing_full):
                self.typing_shown = min(len(self.typing_full),
                                        self.typing_shown + 1)
                self.transcript[-1] = ("fairy",
                                       self.typing_full[:self.typing_shown])
            else:
                self.set_state("ONLINE")
        self.update()

    def _bubble_wanted(self, now):
        return (self.typing_shown < len(self.typing_full)
                or now < self._conv_until
                or now < self._demo_hold_until
                or self.state in ("THINKING", "TALKING"))

    def _full_pack_name(self):
        if self._demo_pack and time.time() < self._demo_hold_until:
            return self._demo_pack
        if time.time() < self._wake_until and self.state not in ("TALKING", "GLITCH"):
            return "stretch"          # she rises, then wakes with a stretch
        st_pack = FULL_STATE_PACK.get(self.state)
        if st_pack:
            return st_pack
        return self._full_pack

    # ---- painting ----------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.draw_sprite(p)
        self.draw_bubble(p)
        self.draw_chip(p)
        p.end()

    def draw_sprite(self, p):
        if self._form > 0.0:
            self._draw_large(p)
        else:
            self._draw_small(p)

    def _draw_small(self, p):
        if self.state != "ONLINE":
            name = ANIM[self.state][0]
        else:
            name = self._pack if self._pack in self.icon_frames else "idle"
        frames = self.icon_frames.get(name) or self.icon_frames["idle"]
        frame = frames[self.fidx % len(frames)]
        s = int(self._scale)
        mode = (Qt.SmoothTransformation if s > 100
                else Qt.FastTransformation)
        pix = frame.scaled(s, s, Qt.KeepAspectRatio, mode)
        x = (W - pix.width()) // 2
        bob = round(1.5 * math.sin(self.pulse_t * 1.8))
        y = H - 70 - pix.height() + bob
        self._pet_pix, self._pet_rect = pix, QRectF(x, y, pix.width(), pix.height())
        self._flash_and_draw(p, pix, x, y)

    def _draw_large(self, p):
        name = self._full_pack_name()
        frames = self.full_frames.get(name) or self.full_frames["idle"]
        frame = frames[self.fidx % len(frames)]
        progress = self._form
        fh = int(LARGE_PX * min(1.0, progress * 1.35))
        fh = max(40, fh)
        pix = frame.scaledToHeight(fh, Qt.SmoothTransformation)
        if pix.width() > W - 24:
            pix = frame.scaledToWidth(W - 24, Qt.SmoothTransformation)
        x = (W - pix.width()) // 2
        base_y = H - 70
        bob = round(1.2 * math.sin(self.pulse_t * 1.8)) if progress >= 1.0 else 0
        y = base_y - pix.height() + bob
        self._pet_pix, self._pet_rect = pix, QRectF(x, y, pix.width(), pix.height())
        # rise mask: while emerging, only the already-risen band is drawn
        vis_top = y if progress >= 1.0 else int(y + pix.height() * (1 - progress))
        src = QRectF(0, vis_top - y, pix.width(), y + pix.height() - vis_top)
        dst = QRectF(x, vis_top, src.width(), src.height())
        p.save()
        p.setOpacity(min(1.0, progress + 0.25))
        p.drawPixmap(dst, pix, src)
        p.restore()
        if progress >= 1.0 and time.time() < self.glitch_until:
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(0.30)
            p.drawPixmap(x - 4, y, pix)
            p.drawPixmap(x + 4, y, pix)
            p.restore()

    def _flash_and_draw(self, p, pix, x, y):
        if time.time() < self.glitch_until:
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(0.30)
            p.drawPixmap(x - 4, y, pix)
            p.drawPixmap(x + 4, y, pix)
            p.restore()
        p.drawPixmap(x, y, pix)

    def _wrapped_lines(self):
        fm = self._fm
        max_w = W - 56
        typing_live = (self.state == "TALKING"
                       and self.typing_shown < len(self.typing_full))
        recent = [(k, t) for k, t in self.transcript[-2:] if t]
        out = []
        for idx, (kind, text) in enumerate(recent):
            last = idx == len(recent) - 1
            prefix0 = "> you: " if kind == "you" else "FAIRY > "
            indent = " " * len(prefix0)
            cur, first = "", True
            for wd in text.split(" "):
                trial = (cur + " " + wd).strip()
                head = prefix0 if first else indent
                if fm.horizontalAdvance(head) + fm.horizontalAdvance(trial) > max_w:
                    if cur:
                        out.append((head, cur, kind))
                        first, cur = False, wd
                    else:
                        out.append((head, wd, kind))
                        first, cur = False, ""
                else:
                    cur = trial
            if cur or first:
                caret = " |" if (last and typing_live) else ""
                out.append((prefix0 if first else indent, cur + caret, kind))
        return out

    def draw_bubble(self, p):
        if not self._bubble_wanted(time.time()):
            self._bubble_rect = None
            return
        wrapped = self._wrapped_lines()
        if not wrapped:
            self._bubble_rect = None
            return
        fm = self._fm
        lh = fm.lineSpacing()
        widest = max(fm.horizontalAdvance(pre + bod) for pre, bod, _ in wrapped)
        bw = min(W - 40, widest) + 26
        bh = 14 + lh * len(wrapped)
        pet_top = self._pet_rect.top() if self._pet_rect else H - 70 - int(self._scale)
        by = max(6, pet_top - bh - 14)
        bx = (W - bw) // 2
        self._bubble_rect = QRectF(bx, by, bw, bh)

        p.setPen(QPen(BUB_EDGE, 1))
        p.setBrush(QBrush(BUB_BG))
        p.drawRoundedRect(bx, by, bw, bh, 5, 5)

        # tail: filled in bubble colour, outlined only along the slants
        cx = W // 2
        y0 = by + bh - 1
        tail_len = max(9, pet_top - y0 - 3)
        tail_w = 7 if tail_len < 40 else 5
        p.setBrush(QBrush(BUB_BG))
        p.drawPolygon(QPolygonF([QPointF(cx - tail_w, y0),
                                 QPointF(cx + tail_w, y0),
                                 QPointF(cx, y0 + tail_len)]))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(cx - tail_w, y0), QPointF(cx, y0 + tail_len))
        p.drawLine(QPointF(cx, y0 + tail_len), QPointF(cx + tail_w, y0))

        # ice corner ticks (Capri's brackets, Fairy's colour)
        p.setPen(QPen(QColor(140, 235, 255, 210), 2))
        L = 9
        for tx, ty, dx, dy in ((bx + 4, by + 4, 1, 1), (bx + bw - 4, by + 4, -1, 1),
                               (bx + 4, by + bh - 4, 1, -1),
                               (bx + bw - 4, by + bh - 4, -1, -1)):
            p.drawLine(tx, ty, tx + L * dx, ty)
            p.drawLine(tx, ty, tx, ty + L * dy)

        yy = by + 7
        for prefix, body, kind in wrapped:
            if kind == "you":
                p.setPen(YOU_COL)
                p.drawText(bx + 13, yy + lh, prefix + body)
            else:
                p.setPen(FAIRY_LBL)
                p.drawText(bx + 13, yy + lh, prefix)
                p.setPen(FAIRY_TXT)
                p.drawText(bx + 13 + fm.horizontalAdvance(prefix), yy + lh, body)
            yy += lh
        p.setPen(Qt.NoPen)

    def draw_chip(self, p):
        if self._ui <= 0.02:
            self._chip_rect = None
            return
        p.save()
        p.setOpacity(self._ui)
        label = f"FAIRY // {self.state}"
        f = QFont(MONO, 9)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f)
        col = CHIP_COLOR.get(self.state, QColor(120, 220, 255))
        fm = p.fontMetrics()
        cw = fm.horizontalAdvance(label) + 34
        cx, cy = W // 2, H - 48
        rect = QRectF(cx - cw // 2, cy - 11, cw, 22)
        self._chip_rect = rect
        p.setPen(QPen(col, 1))
        p.setBrush(QBrush(QColor(6, 9, 16, 225)))
        p.drawRect(rect)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(rect.x() + 8, cy - 3, 6, 6)
        p.setPen(col)
        p.drawText(rect.adjusted(14, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   label)
        if self.state == "TALKING" and self.typing_shown < len(self.typing_full):
            dots = "." * (1 + int(self.pulse_t * 3) % 3)
            p.drawText(rect.adjusted(6, 0, -8, 0),
                       Qt.AlignVCenter | Qt.AlignRight, dots)
        p.setPen(Qt.NoPen)
        p.restore()

    # ---- interaction / dragging ---------------------------------------------
    def _hit_pet(self, pos):
        if self._pet_pix is None or not self._pet_rect.contains(pos):
            return False
        # generous center disc: the ring's HOLE is grabbable too
        if (pos - self._pet_rect.center()).manhattanLength() <= self._pet_rect.width() * 0.45:
            return True
        x = int(pos.x() - self._pet_rect.x())
        y = int(pos.y() - self._pet_rect.y())
        img = self._pet_pix.toImage()
        if 0 <= x < img.width() and 0 <= y < img.height():
            return img.pixelColor(x, y).alpha() > 40
        return False

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.position()
        if (self._hit_pet(pos)
                or (self._bubble_rect and self._bubble_rect.contains(pos))
                or (self._chip_rect and self._chip_rect.contains(pos))):
            self.engage()
            self.drag_off = (e.globalPosition().toPoint()
                             - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self.drag_off is not None and e.buttons() & Qt.LeftButton:
            self.engage()
            self.move(e.globalPosition().toPoint() - self.drag_off)
        elif self._hit_pet(e.position()):
            self.engage()                 # hover: grows, does not emerge

    def _save_pos(self):
        try:  # remember where Master parked her
            with open(os.path.join(HERE, "fairy_position.json"), "w") as f:
                json.dump({"x": self.x(), "y": self.y()}, f)
        except OSError:
            pass

    def _quip_on_move(self, how="drag"):
        if self._move_quip_misses >= 1 or random.random() < 0.65:
            self._move_quip_misses = 0
            line = random.choice(MOVE_QUIPS)
            print(f"[fairy] move-quip({how}): {line}",
                  file=sys.stderr, flush=True)
            self._say(line)
        else:
            self._move_quip_misses += 1

    def mouseReleaseEvent(self, _):
        if self.drag_off is not None:
            self._save_pos()
            self._quip_on_move("drag")
        self.drag_off = None


def run_demo(w, icon_only=False):
    """Cycle expressions on the live window. icon_only = ring-form packs,
    looping forever so every expression can be watched repeatedly."""
    if icon_only:
        names = ["idle", "curious", "sleepy", "attentive", "thinking",
                 "talking", "glitch"]
    else:
        names = ["idle", "curious", "sleepy", "attentive", "thinking",
                 "talking", "glitch", "bust", "stretch", "recline",
                 "surprised"]
    step_ms = 4000

    def resume_idle():
        w._forced_pack = None
        w._demo_pack = None
        w._demo_hold_until = 0.0
        w.engage()
        w.set_state("ONLINE")
        if icon_only:
            QTimer.singleShot(6000, lambda: run_demo(w, icon_only))

    for i, name in enumerate(names):
        QTimer.singleShot(i * step_ms, lambda n=name: w.demo_show(n))
    QTimer.singleShot(len(names) * step_ms, resume_idle)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="FAIRY desktop companion")
    ap.add_argument("--brain", choices=["stub", "discord", "strata"],
                    default="strata")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--strata-url", default=None,
                    help="OpenAI-compatible endpoint (default from "
                         "config.json strata.url, else http://127.0.0.1:8080)")
    ap.add_argument("--pixel", action="store_true",
                    help="pixel-art render for the small ring icon")
    ap.add_argument("--demo", action="store_true",
                    help="cycle every expression, then resume normal idle")
    ap.add_argument("--icon-only", action="store_true",
                    help="keep the small ring form; never emerge full body")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    brain = None
    if args.brain == "discord":
        brain = HermesDiscordBrain(args.config)
    elif args.brain == "strata":
        url = args.strata_url
        if not url:
            try:
                cfg = json.load(open(args.config))
                url = cfg.get("strata", {}).get("url")
            except (OSError, ValueError):
                url = None
        brain = StrataBrain(url=url or "http://127.0.0.1:8080")
    w = FairyWidget(brain=brain, pixel=args.pixel)
    w.icon_only = args.icon_only
    screen = app.primaryScreen().availableGeometry()
    try:
        pos = json.load(open(os.path.join(HERE, "fairy_position.json")))
        x = max(screen.left(), min(int(pos["x"]), screen.right() - W))
        y = max(screen.top(), min(int(pos["y"]), screen.bottom() - H))
        w.move(x, y)
    except (OSError, ValueError, KeyError, TypeError):
        w.move(screen.right() - W + 30, screen.bottom() - H + 20)
    w.show()
    w.transcript.append(("fairy", ""))
    w.typing_full = "Fairy online."
    w.typing_shown = 0
    w._conv_until = time.time() + 6
    w.set_state("TALKING")              # boots with a line in the bubble
    if args.demo:
        QTimer.singleShot(2000, lambda: run_demo(w, args.icon_only))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
