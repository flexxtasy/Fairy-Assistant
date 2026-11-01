#!/usr/bin/env python3
"""Rebuild Fairy as ONE original full-body sprite (sprites/base/fairy.png).

Take the standing-pose panel as the body donor with a strict cutout; where
the face was damaged, graft the head from the clean surprised cutout.
Result: a single consistent character image; make_full.py animates THAT.
"""
from PIL import Image, ImageDraw

SRC = "/home/fairy/Pictures/fairy body.jpg"

im = Image.open(SRC).convert("RGB")
W, H = im.size


def panel(a, b, c, d):
    return im.crop((int(a * W), int(b * H), int(c * W), int(d * H)))


def cutout_strict(p, tol=22):
    p = p.convert("RGB")
    out = p.convert("RGBA")
    w, h = p.size
    px = p.load()

    def clear(x, y):
        out.putpixel((x, y), (0, 0, 0, 0))
    tl, tr = px[0, 0], px[w-1, 0]
    bl, br = px[0, h-1], px[w-1, h-1]

    def field(x, y):
        fx = x / (w - 1)
        fy = y / (h - 1)
        return tuple(int((tl[c_] * (1-fx) + tr[c_] * fx) * (1-fy) +
                         (bl[c_] * (1-fx) + br[c_] * fx) * fy) for c_ in range(3))

    bg = [[False] * h for _ in range(w)]
    for y in range(h):
        for x in range(w):
            f = field(x, y)
            q = px[x, y]
            if abs(q[0]-f[0]) <= tol and abs(q[1]-f[1]) <= tol and abs(q[2]-f[2]) <= tol:
                bg[x][y] = True

    from collections import deque
    keep = [[False] * h for _ in range(w)]
    dq = deque()
    def seed(x, y):
        if bg[x][y] and not keep[x][y]:
            keep[x][y] = True
            dq.append((x, y))
    for y in range(h):
        seed(0, y); seed(w-1, y)
    for x in range(w):
        seed(x, 0); seed(x, h-1)
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if 0 <= nx < w and 0 <= ny < h and bg[nx][ny] and not keep[nx][ny]:
                keep[nx][ny] = True
                dq.append((nx, ny))
    for y in range(h):
        for x in range(w):
            if keep[x][y]:
                clear(x, y)

    # prune small opaque islands
    comp = [[-1] * h for _ in range(w)]
    cid, sizes = 0, []
    for y0 in range(h):
        for x0 in range(w):
            if out.getpixel((x0, y0))[3] > 0 and comp[x0][y0] < 0:
                dq = deque([(x0, y0)])
                comp[x0][y0] = cid
                n = 0
                while dq:
                    x, y = dq.popleft()
                    n += 1
                    for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                        if 0 <= nx < w and 0 <= ny < h and out.getpixel((nx, ny))[3] > 0 \
                                and comp[nx][ny] < 0:
                            comp[nx][ny] = cid
                            dq.append((nx, ny))
                sizes.append(n)
                cid += 1
    if sizes:
        mx = max(sizes)
        for y in range(h):
            for x in range(w):
                c = comp[x][y]
                if c >= 0 and sizes[c] < 0.015 * mx:
                    clear(x, y)
    bbox = out.getbbox()
    return out.crop(bbox)


def measure_torso(cut):
    """Centroid x of her body at chest/waist rows — the graft alignment."""
    w, h = cut.size
    xs = []
    ys = []
    y0, y1 = int(h * 0.38), int(h * 0.50)
    for y in range(y0, y1):
        row = [x for x in range(w) if cut.getpixel((x, y))[3] > 0]
        if row:
            xs.extend(row)
            ys.extend([y])
    return sum(xs) / len(xs), y0, sum(ys) / len(ys)


def graft(standing, head, overlap_y_frac=0.42, head_scale=1.05):
    """One original Fairy: standing body + clean head grafted over the
    shoulder line; anything above that line not covered by the new head
    (grey specks, old tiny head) is deleted."""
    sw, sh = standing.size
    head = head.resize((int(head.width * head_scale),
                        int(head.height * head_scale)), Image.LANCZOS)
    hw, hh = head.size
    cx, chest_y, _ = measure_torso(standing)

    pad_x, pad_y = 30, hh + 10
    canvas = Image.new("RGBA", (max(sw, hw) + 2 * pad_x, sh + 2 * pad_y + sh),
                       (0, 0, 0, 0))
    canvas.alpha_composite(standing, (pad_x, pad_y))

    shoulder = pad_y + int(sh * overlap_y_frac)  # head bottom overlaps chest
    hx = int(cx + pad_x - hw / 2)
    hy = shoulder + 14 - hh

    # delete standing-crop leftovers above the graft line that the head
    # does NOT cover (specks / old head bleed-through)
    for y in range(pad_y, shoulder + 14):
        for x in range(canvas.width):
            if canvas.getpixel((x, y))[3] > 0:
                hx0, hy0 = x - hx, y - hy
                if not (0 <= hx0 < hw and 0 <= hy0 < hh) or \
                        head.getpixel((hx0, hy0))[3] < 120:
                    canvas.putpixel((x, y), (0, 0, 0, 0))

    canvas.alpha_composite(head, (hx, hy))
    return canvas.crop(canvas.getbbox())


def clean_donor(d):
    """Mask out donor leftovers (coords read off the grid QA passes)."""
    w, h = d.size
    px = d.load()

    def lum(c):
        return 0.299 * c[0] + 0.584 * c[1] + 0.114 * c[2]

    def sat(c):
        return max(c) - min(c)

    # protected face/collar box: eyes, brows, dark bodysuit at collar
    fx0, fx1 = int(w * 0.27), int(w * 0.62)
    fy0, fy1 = int(h * 0.30), int(h * 0.65)

    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 0:
                continue
            # (1) neighbouring-panel strip on the right edge
            if x >= 130:
                px[x, y] = (0, 0, 0, 0)
                continue
            c = px[x, y]
            # (2) dark panel background, top-left corner
            if x < 28 and y < 38 and lum(c) < 90:
                px[x, y] = (0, 0, 0, 0)
                continue
            # (3) dark gap between face and glitch tips: dark pixels only,
            #     so hair outline strands inside the gap survive
            if 58 <= x < 105 and y < 45 and lum(c) < 55:
                px[x, y] = (0, 0, 0, 0)
                continue
            # (4) navy panel-bg halo: right-hand strip + bottom-left corner.
            #     NOT applied over the top — that dark arc is her headband.
            L = lum(c)
            br = c[2] - c[0]
            navy = 35 <= L <= 85 and br >= 45
            if navy and ((x >= 95 and y >= 30) or (x < 35 and y >= 105)):
                px[x, y] = (0, 0, 0, 0)

    return d.crop(d.getbbox())


def main():
    import os
    os.makedirs("sprites/base", exist_ok=True)

    standing_raw = panel(0.54, 0.49, 0.752, 0.99)
    standing = cutout_strict(standing_raw)
    standing.save("sprites/base/standing_cut.png")

    # head donor: the smug panel shows her crown + glitch hair tips fully
    smug = cutout_strict(panel(0.335, 0.05, 0.575, 0.48), tol=24)
    smug.save("sprites/base/smug_cut.png")
    head_donor = clean_donor(
        smug.crop((0, 0, smug.width, int(smug.height * 0.60))))
    head_donor.save("sprites/base/head_donor.png")

    base = graft(standing, head_donor, overlap_y_frac=0.40, head_scale=0.95)
    base.save("sprites/base/fairy.png")
    print("standing:", standing.size, "head donor:", head_donor.size,
          "-> base fairy:", base.size)

    sheet = Image.new("RGB", (base.width + 10, base.height + 10), (12, 14, 20))
    sheet.paste(base.convert("RGB"), (5, 5), base)
    sheet.save("sprites/base/qa_base.png")
    print("qa -> sprites/base/qa_base.png")


if __name__ == "__main__":
    main()
