#!/usr/bin/env python3
"""Animate Fairy's ONE original base sprite into full-body packs.

Base: sprites/base/fairy.png (built by make_sprite.py — standing body +
clean head graft; collage used only as reference material).
All eight packs are motion variations of that single sprite, so the large
form is one consistent character, not a set of collage panels.

packs: idle stretch smug curious talking bust surprised recline
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

BASE = "sprites/base/fairy.png"
OUT = "sprites/full"
BASE_H = 230


def load_base():
    im = Image.open(BASE).convert("RGBA")
    s = BASE_H / im.height
    return im.resize((max(1, int(im.width * s)), BASE_H), Image.LANCZOS)


def canvas_size(base):
    return (base.width + 40, BASE_H + 40)


def anchor(base, img, dx=0, dy=0):
    """Bottom-anchor: feet stay on the bar while frames animate."""
    W, H = canvas_size(base)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((W - img.width) // 2 + dx,
                                 H - img.height + 12 + dy))
    return canvas


def squash(base, sx, sy, dx=0, dy=0):
    w, h = base.size
    img = base.resize((max(1, int(w * sx)), max(1, int(h * sy))), Image.LANCZOS)
    return anchor(base, img, dx, dy)


def rot(base, deg, dx=0, dy=0):
    img = base.rotate(deg, Image.BICUBIC, expand=True)
    return anchor(base, img, dx, dy)


def save_seq(pack, frames):
    d = os.path.join(OUT, pack)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    for i, f in enumerate(frames):
        f.save(os.path.join(d, f"frame_{i:02d}.png"))
    print(f"  {pack}: {len(frames)} frames")


def main():
    if not os.path.exists(BASE):
        raise SystemExit("run make_sprite.py first (builds the base sprite)")
    base = load_base()
    print("base sprite:", base.size, "-> all packs animate from this one")

    two = math.pi * 2

    # idle: breathe + micro bob
    save_seq("idle", [squash(base, 1 - 0.014 * math.sin(two * i / 12),
                             1 + 0.022 * math.sin(two * i / 12),
                             dy=round(-1.3 * math.sin(two * (i / 12 + 0.25)))
                             ) for i in range(12)])

    # stretch: waking rise — elongate + backward lean, feet anchored
    frames = []
    for i in range(10):
        p = math.pi * i / 9
        img = base.resize((max(1, int(base.width * (1 - 0.03 * math.sin(p)))),
                           max(1, int(base.height * (1 + 0.07 * math.sin(p))))),
                          Image.LANCZOS)
        img = img.rotate(2.5 * math.sin(p), Image.BICUBIC, expand=True)
        W, H = canvas_size(base)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.alpha_composite(img, ((W - img.width) // 2,
                                     H - img.height + 10))
        frames.append(canvas)
    save_seq("stretch", frames)

    # smug: dry half-lidded rock
    save_seq("smug", [rot(base, 2.5 * math.sin(two * i / 10),
                          dx=round(1.5 * math.sin(two * i / 10)))
                      for i in range(10)])

    # curious: bigger tilt + lateral drift
    save_seq("curious", [rot(base, 5.0 * math.sin(two * i / 12),
                             dx=round(4 * math.sin(two * i / 12)))
                         for i in range(12)])

    # talking: speech bob + squash
    save_seq("talking", [squash(base, 1 - 0.022 * math.sin(two * 2 * i / 14),
                                1 + 0.030 * math.sin(two * 2 * i / 14),
                                dy=-round(5 * math.sin(two * i / 14)))
                         for i in range(14)])

    # bust: zoomed head+collar variant for parked ONLINE moments
    crop = base.crop((0, 0, base.width, int(base.height * 0.58)))
    s = BASE_H / crop.height
    crop = crop.resize((int(crop.width * s), BASE_H), Image.LANCZOS)
    save_seq("bust", [rot(crop, 1.8 * math.sin(two * i / 10),
                          dx=round(3 * math.sin(two * i / 10)),
                          dy=round(-1 * math.sin(two * i / 10)))
                      for i in range(10)])

    # surprised: pop-in wobble with a one-frame RGB-split flicker
    frames = []
    for i in range(8):
        k = (1.08, 1.03, 1.05, 1.015, 0.96, 0.985, 1.0, 1.0)[i]
        fr = squash(base, k, k, dx=(3 if i % 2 else -3) if i < 5 else 0)
        if i in (1, 3):
            r, g, b, a = fr.split()
            mix = Image.merge("RGBA", (r, b, g, a))
            fr = Image.alpha_composite(fr, mix)
        frames.append(fr)
    save_seq("surprised", frames)

    # recline: parked rest — slight lean, slow settle
    save_seq("recline", [rot(base, -3.5 - 1.2 * math.sin(two * i / 12),
                             dy=round(3 * math.sin(two * i / 12)))
                         for i in range(12)])

    # contact sheet QA
    names = ["idle", "stretch", "smug", "curious", "talking", "bust",
             "surprised", "recline"]
    cols = 4
    w, h = 150, 175
    sheet = Image.new("RGB", (cols * w, 2 * h), (12, 14, 20))
    dr = ImageDraw.Draw(sheet)
    for idx, name in enumerate(names):
        im2 = Image.open(os.path.join(OUT, name, "frame_00.png"))
        cw, ch = im2.size
        s = min((w - 12) / cw, (h - 26) / ch)
        im2 = im2.resize((max(1, int(cw * s)), max(1, int(ch * s))),
                         Image.LANCZOS)
        x, y = (idx % cols) * w, (idx // cols) * h
        sheet.paste(im2.convert("RGB"), (x + 6, y + 18), im2)
        dr.text((x + 6, y + 2), name, fill=(220, 220, 90))
    sheet.save(os.path.join(OUT, "sheet.png"))
    print("contact sheet ->", os.path.join(OUT, "sheet.png"))


if __name__ == "__main__":
    main()
