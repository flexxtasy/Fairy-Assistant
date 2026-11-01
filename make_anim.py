#!/usr/bin/env python3
"""Turn the static NPC_Fairy.webp into animated sprite-frame packs.

Two render variants:
  sprites/anim/        - smooth cutout
  sprites/anim_pixel/  - chunky pixel-art version (posterize + nearest upscale)

Expression packs per variant:
  idle       - breathe + bob + periodic blink
  attentive  - wide pupil, alert lean
  curious    - head tilt, wide pupil, inquisitive bob
  sleepy     - half-closed lids, slow heavy bob
  thinking   - faster rotate sway
  talking    - happy double bob with squash bounce
  glitch     - RGB split + slice displacement

All frames are transparent-background PNGs.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageOps

SRC = "/home/fairy/Pictures/RandomPics/NPC_Fairy.webp"
SS = 3  # supersample factor for smooth mask


def base_cutout():
    im = Image.open(SRC).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    big = im.resize((s * SS, s * SS), Image.LANCZOS)
    # circle mask covering ~94% of the square, feathered edge
    m = Image.new("L", big.size, 0)
    d = ImageDraw.Draw(m)
    pad = int(s * SS * 0.03)
    d.ellipse((pad, pad, big.width - pad, big.height - pad), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(s * SS * 0.012))
    im = big.convert("RGBA")
    im.putalpha(m)
    im = im.resize((s, s), Image.LANCZOS)
    bbox = im.getbbox()
    return im.crop(bbox)


def pixelate(base, px=48, bits=4):
    """Chunky pixel-art version of the cutout, alpha kept hard."""
    w, h = base.size
    small = base.resize((px, px), Image.LANCZOS)
    alpha = small.split()[3]
    small = ImageOps.posterize(small.convert("RGB"), bits)
    big = small.convert("RGB").resize((w, h), Image.NEAREST).convert("RGBA")
    big.putalpha(alpha.resize((w, h), Image.NEAREST).point(
        lambda v: 255 if v > 96 else 0))
    return big


def pupil_info(im):
    """Locate the white pupil dot: brightest blob in the inner half."""
    g = im.convert("L")
    w, h = im.size
    px = g.load()
    sx = sy = n = 0
    minx = miny = 10**9
    maxx = maxy = -1
    for y in range(h // 3, 2 * h // 3):
        for x in range(w // 3, 2 * w // 3):
            if px[x, y] > 215:
                sx += x; sy += y; n += 1
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    if n < 8:
        return None
    cx, cy = sx // n, sy // n
    # second pass: only pixels near the blob centre, so white-ring edges
    # don't inflate the radius
    sx = sy = n = 0
    minx = miny = 10**9
    maxx = maxy = -1
    for y in range(h // 3, 2 * h // 3):
        for x in range(w // 3, 2 * w // 3):
            if px[x, y] > 215 and (x - cx) ** 2 + (y - cy) ** 2 < 6400:
                sx += x; sy += y; n += 1
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    if n < 8:
        return None
    cx, cy = sx // n, sy // n
    r = min(max(maxx - minx, maxy - miny) // 2 + 1,
            int((n / math.pi) ** 0.5) + 2)
    # iris colour: sample the blue ring gap just left of the dot
    dp = im.convert("RGB").load()
    lid = dp[max(0, cx - r - 25), cy]
    return cx, cy, r, lid


def redraw_pupil(im, info, mode, chunky=False):
    """mode: blink = full iris-colour lid; half = half-closed top lid;
    wide = enlarged white dot."""
    cx, cy, r, lid = info
    out = im.copy()
    d = ImageDraw.Draw(out)
    if mode in ("blink", "half"):
        r2 = r + 16          # cover the whole dot incl. its soft edge
        lid_layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lid_layer)
        if mode == "blink":
            dl.ellipse((cx - r2, cy - r2, cx + r2, cy + r2),
                       fill=tuple(lid) + (255,))
        else:  # half-closed: lid drops over the top of the dot
            dl.rectangle((cx - r2, cy - r2, cx + r2, cy - r // 4),
                         fill=tuple(lid) + (255,))
            dl.ellipse((cx - r2, cy - r // 4 - 6, cx + r2, cy + r2 // 2),
                       fill=tuple(lid) + (255,))
        if not chunky:
            lid_layer = lid_layer.filter(ImageFilter.GaussianBlur(3))
        out.alpha_composite(lid_layer)
    elif mode == "wide":
        r3 = r + 7          # clearly enlarged, not a subtle bump
        d.ellipse((cx - r3, cy - r3, cx + r3, cy + r3),
                  fill=(245, 248, 255, 255))
    return out


def paste_on(base, dx=0, dy=0, scale=1.0, rot=0.0):
    img = base
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if scale != 1.0:
        w, h = img.size
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                         Image.LANCZOS)
    W = base.width + 24
    H = base.height + 24
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox = (W - img.width) // 2 + dx
    oy = (H - img.height) // 2 + dy
    canvas.alpha_composite(img, (ox, oy))
    return canvas


def rgb_split(base, dx=4):
    r, g, b = base.split()[:3]
    out = Image.new("RGBA", (base.width + 2 * dx, base.height), (0, 0, 0, 0))
    rr = Image.merge("RGBA", (r, Image.new("L", base.size, 0),
                              Image.new("L", base.size, 0), r))
    bb = Image.merge("RGBA", (Image.new("L", base.size, 0),
                              Image.new("L", base.size, 0), b, b))
    out.alpha_composite(rr, (0, 0))
    out.alpha_composite(base, (dx, 0))
    out.alpha_composite(bb, (2 * dx, 0))
    return out


def slice_shift(base, n=3, maxoff=10):
    out = base.copy()
    w, h = base.size
    for _ in range(n):
        y0 = random.randint(h // 4, 3 * h // 4 - 12)
        band = base.crop((0, y0, w, y0 + random.randint(3, 12)))
        off = random.choice([-1, 1]) * random.randint(3, maxoff)
        out.alpha_composite(band, (off, y0))
    return out


def save_seq(outdir, state, frames):
    d = os.path.join(outdir, state)
    os.makedirs(d, exist_ok=True)
    for i, f in enumerate(frames):
        f.save(os.path.join(d, f"frame_{i:02d}.png"))
    print(f"  {state}: {len(frames)} frames")


def build(outdir, base, info, chunky=False):
    # idle: 12-frame breathe+bob, blink on 9-10
    seq = []
    for i in range(12):
        t = i / 12
        img = base
        if info and i in (9, 10):
            img = redraw_pupil(img, info, "blink", chunky)
        dy = round(2 * math.sin(2 * math.pi * t))
        sc = 1.0 + 0.018 * math.sin(2 * math.pi * (t + 0.25))
        seq.append(paste_on(img, dy=dy, scale=sc))
    save_seq(outdir, "idle", seq)

    # attentive: wide pupil, small forward lean
    seq = []
    for i in range(8):
        img = redraw_pupil(base, info, "wide", chunky) if info else base
        dy = round(1.5 * math.sin(2 * math.pi * i / 8))
        seq.append(paste_on(img, dy=dy, scale=1.02))
    save_seq(outdir, "attentive", seq)

    # curious: 8-deg head tilt rock, wide pupil, inquisitive bob
    seq = []
    for i in range(10):
        t = i / 10
        img = redraw_pupil(base, info, "wide", chunky) if info else base
        rot = 8 * math.sin(math.pi * t)          # slow rock one way and back
        dy = round(1.8 * math.sin(2 * math.pi * t))
        seq.append(paste_on(img, dy=dy, rot=rot))
    save_seq(outdir, "curious", seq)

    # sleepy: half lids, slow heavy bob
    seq = []
    for i in range(10):
        t = i / 10
        img = redraw_pupil(base, info, "half", chunky) if info else base
        dy = round(2.5 * math.sin(2 * math.pi * t * 0.6))
        rot = 1.5 * math.sin(2 * math.pi * t * 0.6)
        seq.append(paste_on(img, dy=dy, rot=rot))
    save_seq(outdir, "sleepy", seq)

    # thinking: faster sway with rotation
    seq = []
    for i in range(12):
        t = i / 12
        rot = 4 * math.sin(2 * math.pi * t)
        dx = round(3 * math.sin(2 * math.pi * t + 1.2))
        seq.append(paste_on(base, dx=dx, rot=rot))
    save_seq(outdir, "thinking", seq)

    # talking: happy double bob with squash bounce
    seq = []
    for i in range(14):
        t = i / 14
        img = base
        if info and i % 7 == 6:
            img = redraw_pupil(img, info, "blink", chunky)
        w0, h0 = paste_on(img).size
        big = paste_on(img)
        dy = round(3 * math.sin(2 * math.pi * 2 * t))
        sq = 1.0 + 0.05 * math.sin(2 * math.pi * 2 * t)
        big = big.resize((int(big.width * sq), int(big.height * (2 - sq))),
                         Image.LANCZOS)
        canvas = Image.new("RGBA", (w0, h0), (0, 0, 0, 0))
        canvas.alpha_composite(big, ((w0 - big.width) // 2,
                                     h0 - big.height + dy))
        seq.append(canvas)
    save_seq(outdir, "talking", seq)

    # glitch: RGB split + slice displacement, harsher mid-burst
    seq = []
    for i in range(8):
        k = 2 if i in (3, 4) else 1
        img = rgb_split(base, dx=(2 if chunky else 4) * k)
        if i % 2 == 0:
            img = slice_shift(img, n=k, maxoff=12)
        seq.append(paste_on(img.resize(base.size, Image.LANCZOS),
                            dx=random.randint(-3, 3)))
    save_seq(outdir, "glitch", seq)


def main():
    base = base_cutout()
    info = pupil_info(base)
    print("smooth base:", base.size, "pupil:", info)
    build("sprites/anim", base, info)

    pbase = pixelate(base)
    pinfo = pupil_info(pbase)
    if pinfo is None and info is not None:
        # posterize dimmed the dot: reuse geometry, resample colours from pbase
        cx, cy, r, _ = info
        dp = pbase.convert("RGB").load()
        pinfo = (cx, cy, r, tuple(dp[max(0, cx - r - 25), cy]))
        print("pixel pupil: reused smooth geometry", pinfo)
    print("pixel base:", pbase.size, "pupil:", pinfo)
    build("sprites/anim_pixel", pbase, pinfo, chunky=True)
    print("done")


if __name__ == "__main__":
    main()
