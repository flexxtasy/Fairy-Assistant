#!/usr/bin/env python3
"""Render a clean demo GIF from the CURRENT Fairy widget (offscreen).
Segments: idle-at-rest -> hover reveal -> thinking -> typed quip -> glitch.
Run: QT_QPA_PLATFORM=offscreen python3 make_demo_gif.py
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import fairy
from PySide6.QtGui import QImage


class QuietBrain:
    def reply(self, t):
        return "hm"


app = QApplication([])
w = fairy.FairyWidget(brain=QuietBrain())
w.icon_only = True
w.move(400, 400)
w.show()
w.grab()  # first paint (sets _pet_rect)

frames, durs = [], []


def snap(dur_ms):
    pix = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    img = QImage(pix)  # keep alive
    from PIL import Image as PImage
    frame = PImage.frombytes("RGBA", (img.width(), img.height()),
                             img.constBits()[:img.sizeInBytes()])
    frames.append(frame.convert("P", palette=PImage.Palette.ADAPTIVE,
                               colors=255))
    durs.append(dur_ms)


def pump(n, dur_ms, extra=0):
    for _ in range(n):
        w.tick()
        snap(dur_ms)


# 1) at rest: ring only, chrome hidden (v7 default look)
w._ui = 0.0
w._hover_check = lambda: None      # freeze hover logic for the capture
pump(14, 110)

# 2) hover reveal: chip + input fade in, she grows a little
w.engage()
for i in range(12):
    w._ui = min(1.0, w._ui + 0.09)
    w._ui_eff.setOpacity(w._ui)
    if w._ui > 0.0 and not w.input.isVisible():
        w.input.setVisible(True)
    w.tick()
    snap(80)

# 3) thinking
w.set_state("THINKING")
pump(10, 90)

# 4) she speaks (current persona voice, typewriter live)
w._say("Relocated. I approve of the new view.")
for _ in range(46):
    w.tick()
    snap(70)

# 5) glitch
w.glitch_until = time.time() + 3
w.set_state("GLITCH")
pump(10, 85)
w.glitch_until = 0

# 6) settle back to idle, chrome fades out
w.set_state("ONLINE")
w.engage()
for i in range(12):
    w._ui = max(0.0, w._ui - 0.09)
    w._ui_eff.setOpacity(w._ui)
    if w._ui <= 0.0 and w.input.isVisible():
        w.input.setVisible(False)
    w.tick()
    snap(90)

out = os.path.join(fairy.HERE, "demo_fairy_v7.gif")
frames[0].save(out, save_all=True, append_images=frames[1:],
              duration=durs, loop=0, optimize=True)
size_mb = os.path.getsize(out) / 1e6
print(f"saved {out}: {len(frames)} frames, {size_mb:.1f} MB")
