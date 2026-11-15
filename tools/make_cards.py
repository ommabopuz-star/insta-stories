"""
Istoriya kartochkalarini lokal yasash (1080×1920 JPG) va navbatga qo'yish.

  tools\\storyvenv\\Scripts\\python.exe -X utf8 tools\\make_cards.py content\\2026-11-16.json

Kontent JSON: {"items":[{id,type,date,...}]}
  fact : title ({so'z} = urg'u), body, [tag]
  poll : question, a, b
  reels: cover (rasm yo'li), title, [subtitle]
Har kartochka o'z mavzusi va kompozitsiyasini oladi (bir xil shablon takrorlanmaydi).
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path(r"D:\AI Video Editor\Brand\fonts")
W, H = 1080, 1920
SAFE_TOP, SAFE_BOT = 260, 1580  # Instagram UI yopmaydigan hudud
HANDLE = "@muhammadjon_texno"

THEMES = [
    # nom, fon1, fon2, matn, ikkinchi matn, aksent, urg'u
    dict(name="navy", bg1=(11, 16, 38), bg2=(24, 30, 78), fg=(240, 244, 255), fg2=(170, 182, 220),
         acc=(29, 233, 182), hi=(255, 92, 108)),
    dict(name="paper", bg1=(244, 243, 239), bg2=(232, 230, 222), fg=(30, 33, 64), fg2=(92, 96, 128),
         acc=(29, 158, 117), hi=(224, 79, 95)),
    dict(name="indigo", bg1=(36, 38, 120), bg2=(75, 79, 224), fg=(255, 255, 255), fg2=(208, 212, 255),
         acc=(29, 233, 182), hi=(255, 214, 102)),
    dict(name="ink", bg1=(18, 20, 26), bg2=(34, 38, 48), fg=(245, 245, 245), fg2=(160, 166, 180),
         acc=(255, 196, 0), hi=(255, 92, 108)),
    dict(name="mint", bg1=(222, 250, 241), bg2=(196, 240, 226), fg=(16, 40, 48), fg2=(60, 96, 104),
         acc=(75, 79, 224), hi=(224, 79, 95)),
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def uz(s: str) -> str:
    """O'zbek apostroflari: o'/g' → U+2018, qolgan tutuq → U+2019 (Manrope'da ʻ yo'q)."""
    s = re.sub(r"([oOgG])['ʻ‘`]", "\\1‘", s)
    return re.sub(r"['ʼ`]", "’", s)


def gradient(t: dict, angle: float) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    ca, sa = math.cos(angle), math.sin(angle)
    span = abs(W * ca) + abs(H * sa)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            k = ((x - W / 2) * ca + (y - H / 2) * sa) / span + 0.5
            c = tuple(int(t["bg1"][i] + (t["bg2"][i] - t["bg1"][i]) * k) for i in range(3))
            px[x, y] = c
            if x + 1 < W:
                px[x + 1, y] = c
            if y + 1 < H:
                px[x, y + 1] = c
                if x + 1 < W:
                    px[x + 1, y + 1] = c
    return img


def decor(img: Image.Image, t: dict, rng: random.Random) -> None:
    """Fon bezagi: har safar boshqacha (sxema chiziqlari / doiralar / nuqtalar)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kind = rng.choice(["circuit", "rings", "dots", "bars"])
    a = (*t["acc"], 46)
    if kind == "circuit":
        for _ in range(9):
            x, y = rng.randrange(0, W), rng.randrange(0, H)
            pts = [(x, y)]
            for _ in range(rng.randint(2, 4)):
                if rng.random() < .5:
                    x += rng.choice([-1, 1]) * rng.randint(80, 260)
                else:
                    y += rng.choice([-1, 1]) * rng.randint(80, 260)
                pts.append((x, y))
            d.line(pts, fill=a, width=4)
            d.ellipse([x - 10, y - 10, x + 10, y + 10], outline=a, width=4)
    elif kind == "rings":
        cx, cy = rng.choice([(W, 0), (0, H), (W, H * .55), (0, H * .3)])
        for r in range(160, 1400, 110):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*t["acc"], 34), width=3)
    elif kind == "dots":
        for y in range(40, H, 54):
            for x in range(40, W, 54):
                if rng.random() < .55:
                    d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(*t["fg2"], 40))
    else:
        for i in range(7):
            x = rng.randrange(-200, W)
            d.rectangle([x, 0, x + rng.randint(20, 90), H], fill=(*t["acc"], 16))
        layer = layer.rotate(rng.choice([-18, 18]), resample=Image.BICUBIC)
    # yumshoq aksent yorug'lik
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gx, gy = rng.choice([(W * .85, H * .2), (W * .15, H * .8), (W * .5, H * .1)])
    gd.ellipse([gx - 420, gy - 420, gx + 420, gy + 420], fill=(*t["acc"], 40))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img.paste(Image.alpha_composite(Image.alpha_composite(img.convert("RGBA"), glow), layer).convert("RGB"))


def wrap_rich(draw, text: str, fnt, maxw: int):
    """*urg'u* belgilari bilan so'zlarni qatorlarga bo'lish → [[(so'z, urg'u?)]]."""
    # so'z = [(bo'lak, urg'u?)…]; "{5 GHz}?" dagi "?" oldingi so'zga bo'shliqsiz yopishadi.
    # NBSP ( ) so'zni bo'lmaydi: "10 000".
    words: list[list] = []
    for part in re.split(r"(\{[^}]+\})", text):
        if not part:
            continue
        hi = part.startswith("{") and part.endswith("}")
        body = part[1:-1] if hi else part
        toks = body.split(" ")
        for i, w in enumerate(toks):
            if not w:
                continue
            if i == 0 and words and not part.startswith(" ") and not hi:
                words[-1].append((w, hi))  # tinish belgisi yopishadi
            else:
                words.append([(w, hi)])
    def wlen(wd):
        return sum(draw.textlength(s, font=fnt) for s, _ in wd)
    sp = draw.textlength(" ", font=fnt)
    lines, cur, curw = [], [], 0.0
    for wd in words:
        add = wlen(wd) + (sp if cur else 0)
        if cur and curw + add > maxw:
            lines.append(cur)
            cur, curw = [wd], wlen(wd)
        else:
            cur.append(wd)
            curw += add
    if cur:
        lines.append(cur)
    return lines


def draw_rich(draw, lines, fnt, x0, y, t, lh, align="left", maxw=0):
    sp = draw.textlength(" ", font=fnt)
    for ln in lines:
        lw = sum(draw.textlength(s, font=fnt) for wd in ln for s, _ in wd) + sp * (len(ln) - 1)
        x = x0 + (maxw - lw) / 2 if align == "center" else x0
        for wd in ln:
            for s, hi in wd:
                draw.text((x, y), s.replace(" ", " "), font=fnt, fill=t["hi"] if hi else t["fg"])
                x += draw.textlength(s, font=fnt)
            x += sp
        y += lh
    return y


def fit_title(draw, text, maxw, maxh, start=96, minimum=58):
    for size in range(start, minimum - 1, -4):
        f = font("Unbounded-ExtraBold.ttf", size)
        lines = wrap_rich(draw, text, f, maxw)
        lh = int(size * 1.22)
        sp = draw.textlength(" ", font=f)
        widest = max(sum(draw.textlength(s, font=f) for wd in ln for s, _ in wd) + sp * (len(ln) - 1)
                     for ln in lines)
        if len(lines) * lh <= maxh and widest <= maxw:
            return f, lines, lh
    return f, lines, lh


def wrap_plain(draw, text, fnt, maxw):
    plain = text.replace("{", "").replace("}", "")
    return [" ".join("".join(s for s, _ in wd) for wd in ln).replace(" ", " ")
            for ln in wrap_rich(draw, plain, fnt, maxw)]


def chip(draw, xy, text, t, fill=None, fg=None, size=34):
    f = font("Manrope-ExtraBold.ttf", size)
    x, y = xy
    w = draw.textlength(text, font=f)
    draw.rounded_rectangle([x, y, x + w + 48, y + size + 30], radius=(size + 30) // 2,
                           fill=fill or t["acc"])
    draw.text((x + 24, y + 12), text, font=f, fill=fg or t["bg1"])
    return x + w + 48


def brand_mark(draw, t, y=SAFE_BOT + 70):
    f = font("JetBrainsMono-Bold.ttf", 34)
    w = draw.textlength(HANDLE, font=f)
    draw.text(((W - w) / 2, y), HANDLE, font=f, fill=t["fg2"])


# ───────────── kartochka turlari ─────────────
def card_fact(it, t, rng, n):
    img = gradient(t, rng.uniform(0, math.pi))
    decor(img, t, rng)
    d = ImageDraw.Draw(img)
    M = 88
    layout = rng.choice(["top", "center", "number"])
    chip(d, (M, SAFE_TOP), uz(it.get("tag", f"TEXNO-FAKT #{n}")).upper(), t)
    if layout == "number":
        big = font("Unbounded-ExtraBold.ttf", 420)
        num = f"{n:02d}"
        d.text((W - M - d.textlength(num, font=big) + 30, SAFE_TOP - 40), num, font=big,
               fill=tuple(int(c * .5 + b * .5) for c, b in zip(t["bg2"], t["bg1"])))
    tf, tl, lh = fit_title(d, uz(it["title"]), W - 2 * M, 620, start=112)
    bf = font("Manrope-Bold.ttf", 54)
    body = wrap_plain(d, uz(it["body"]), bf, W - 2 * M)
    total = len(tl) * lh + 102 + len(body) * 78
    top, bottom = SAFE_TOP + 170, SAFE_BOT - 110
    # bo'sh joyni teng taqsimlash (yuqoriga biroz og'ib)
    y0 = top + max(0, (bottom - top - total)) * (0.25 if layout == "top" else 0.42)
    y = draw_rich(d, tl, tf, M, y0, t, lh)
    y += 30
    d.rounded_rectangle([M, y, M + 140, y + 12], radius=6, fill=t["acc"])
    y += 60
    for ln in body:
        d.text((M, y), ln, font=bf, fill=t["fg2"])
        y += 78
    foot = uz(it.get("foot", "Saqlab qo'ying — kerak bo'ladi"))
    ff = font("Manrope-ExtraBold.ttf", 38)
    d.text((M, SAFE_BOT - 30), foot, font=ff, fill=t["acc"])
    brand_mark(d, t)
    return img


def card_poll(it, t, rng, n):
    img = gradient(t, rng.uniform(0, math.pi))
    decor(img, t, rng)
    d = ImageDraw.Draw(img)
    M = 88
    cw = chip(d, (M, SAFE_TOP), "SO'ROVNOMA".replace("'", "‘"), t)
    tf, tl, lh = fit_title(d, uz(it["question"]), W - 2 * M, 470, start=104)
    total = len(tl) * lh + 90 + 2 * 240
    top, bottom = SAFE_TOP + 170, SAFE_BOT - 150
    y = top + max(0, bottom - top - total) * 0.4
    y = draw_rich(d, tl, tf, M, y, t, lh) + 90
    of = font("Unbounded-ExtraBold.ttf", 60)
    lf = font("Manrope-ExtraBold.ttf", 52)
    for letter, key in (("A", "a"), ("B", "b")):
        box = [M, y, W - M, y + 200]
        d.rounded_rectangle(box, radius=44, outline=t["acc"], width=6,
                            fill=tuple(int(c * .85 + a * .15) for c, a in zip(t["bg1"], t["acc"])))
        d.ellipse([M + 34, y + 40, M + 154, y + 160], fill=t["acc"])
        lw = d.textlength(letter, font=of)
        d.text((M + 94 - lw / 2, y + 56), letter, font=of, fill=t["bg1"])
        lines = wrap_plain(d, uz(it[key]), lf, W - 2 * M - 230)
        ty = y + 100 - len(lines) * 36
        for ln in lines:
            d.text((M + 190, ty), ln, font=lf, fill=t["fg"])
            ty += 68
        y += 240
    hf = font("Manrope-ExtraBold.ttf", 40)
    hint = uz(it.get("foot", "A yoki B? Javobni DM'ga yozing"))
    d.text((M, SAFE_BOT - 30), hint, font=hf, fill=t["hi"])
    brand_mark(d, t)
    return img


def card_reels(it, t, rng, n):
    img = gradient(t, rng.uniform(0, math.pi))
    cover = Image.open(it["cover"]).convert("RGB")
    # orqa fon: xira muqova
    bg = cover.resize((W, int(W * cover.height / cover.width)) if cover.width / cover.height > W / H
                      else (int(H * cover.width / cover.height), H))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, bg, .55)
    d = ImageDraw.Draw(img)
    cw_, ch_ = 760, int(760 * cover.height / cover.width)
    ch_ = min(ch_, 1000)
    cv = cover.resize((cw_, int(cw_ * cover.height / cover.width)))
    cv = cv.crop((0, (cv.height - ch_) // 2, cw_, (cv.height - ch_) // 2 + ch_))
    mask = Image.new("L", cv.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *cv.size], radius=44, fill=255)
    x0, y0 = (W - cw_) // 2, SAFE_TOP + 130
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 10, y0 + 24, x0 + cw_ + 10, y0 + ch_ + 24],
                                             radius=44, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(24))).convert("RGB")
    img.paste(cv, (x0, y0), mask)
    d = ImageDraw.Draw(img)
    label = "YANGI VIDEO"
    f = font("Manrope-ExtraBold.ttf", 36)
    lw = d.textlength(label, font=f) + 48
    chip(d, ((W - lw) / 2, SAFE_TOP), label, t, fill=t["hi"], fg=(255, 255, 255), size=36)
    tf, tl, lh = fit_title(d, uz(it["title"]), W - 160, 300, start=72, minimum=48)
    y = draw_rich(d, tl, tf, 80, y0 + ch_ + 60, t, lh, align="center", maxw=W - 160)
    if it.get("subtitle"):
        sf = font("Manrope-Bold.ttf", 42)
        for ln in wrap_plain(d, uz(it["subtitle"]), sf, W - 160):
            lw = d.textlength(ln, font=sf)
            d.text(((W - lw) / 2, y + 10), ln, font=sf, fill=t["fg2"])
            y += 58
    brand_mark(d, t)
    return img


RENDER = {"fact": card_fact, "poll": card_poll, "reels": card_reels}


def main():
    src = Path(sys.argv[1])
    data = json.loads(src.read_text(encoding="utf-8"))
    out_ids = []
    last_theme = None
    fact_no = data.get("start_number", 1) - 1
    for it in data["items"]:
        if it["type"] == "fact":
            fact_no += 1
        n = fact_no
        rng = random.Random(it["id"])
        choices = [t for t in THEMES if t["name"] != last_theme]
        t = next((x for x in THEMES if x["name"] == it.get("theme")), None) or rng.choice(choices)
        last_theme = t["name"]
        img = RENDER[it["type"]](it, t, rng, n)
        d = ROOT / "stories" / it["id"]
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / "story.jpg", quality=90, optimize=True, progressive=True)
        meta = {"type": it["type"], "media": "story.jpg", "date": it.get("date"),
                "priority": it.get("priority", 0), "note": it.get("note", "")}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out_ids.append(f"{it['id']} ({it['type']}, {t['name']})")
    print("Tayyor:\n  " + "\n  ".join(out_ids))


if __name__ == "__main__":
    main()
