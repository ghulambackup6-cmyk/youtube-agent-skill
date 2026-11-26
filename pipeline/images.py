"""Make one picture per scene.

Three sources, in this order of preference for each scene:
1. Your own file. Drop images/scene_07.png (or .jpg, or a .mp4 clip such as a 3D shot made
   with /3d-animator) into the video folder and it is never overwritten.
2. A free AI generator (Pollinations, no key, no account). Used with --generate.
3. A placeholder card showing the prompt, so the video still renders and you can see what is
   missing.

Text scenes ("Text: ..." or a quoted line in ON SCREEN) are always drawn here, never by the AI,
because AI image models misspell words.
"""
import hashlib
import textwrap
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
import os


def _first(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0]


WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FONT_BOLD = _first("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                   os.path.join(WINFONTS, "georgiab.ttf"), os.path.join(WINFONTS, "arialbd.ttf"),
                   "/System/Library/Fonts/Supplemental/Georgia Bold.ttf")
FONT = _first("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              os.path.join(WINFONTS, "segoeui.ttf"), os.path.join(WINFONTS, "arial.ttf"),
              "/System/Library/Fonts/Supplemental/Arial.ttf")

# Colours and the style sentence added to every prompt, per series (channel/series.md).
STYLES = {
    "Unseen Explained": {"bg": (12, 20, 45), "accent": (212, 175, 55),
                         "style": "cinematic digital painting, deep navy blue and gold palette, "
                                  "soft volumetric light, mysterious, reverent"},
    "Night Tales": {"bg": (8, 8, 10), "accent": (190, 30, 30),
                    "style": "dark atmospheric horror illustration, near-black with red and pale "
                             "white accents, fog, moonlight, cinematic"},
    "Forgotten Pages": {"bg": (40, 30, 18), "accent": (30, 110, 70),
                        "style": "painterly historical illustration, sand, parchment and deep "
                                 "green tones, documentary feel, golden hour"},
}
DEFAULT = STYLES["Unseen Explained"]
NEGATIVE = "no text, no letters, no watermark, no gore, no visible faces on religious figures"


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def style_for(series):
    return STYLES.get(series, DEFAULT)


def find_existing(folder, sid):
    for ext in (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"):
        p = folder / f"{sid}{ext}"
        if p.exists():
            return p
    return None


def gradient(bg):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = 1 - abs(y - H / 2) / (H / 2)
        d.line([(0, y), (W, y)], fill=tuple(min(255, int(c + 25 * k)) for c in bg))
    return img


def text_card(text, st, out):
    img = gradient(st["bg"])
    d = ImageDraw.Draw(img)
    size = 120 if len(text) < 20 else 84
    f = font(FONT_BOLD, size)
    lines = textwrap.wrap(text, 24 if size == 84 else 16)
    total = len(lines) * int(size * 1.25)
    y = (H - total) // 2
    for line in lines:
        w = d.textlength(line, font=f)
        d.text(((W - w) / 2, y), line, font=f, fill=st["accent"])
        y += int(size * 1.25)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img.save(out)


def placeholder(scene, st, out):
    img = gradient(st["bg"])
    d = ImageDraw.Draw(img)
    d.text((80, 70), f"PLACEHOLDER  {scene['id']}", font=font(FONT_BOLD, 54), fill=st["accent"])
    y = 190
    for line in textwrap.wrap(scene["visual"], 60)[:8]:
        d.text((80, y), line, font=font(FONT, 44), fill=(230, 230, 230))
        y += 60
    d.text((80, H - 110), f"Replace with your own image: images/{scene['id']}.png",
           font=font(FONT, 36), fill=(160, 160, 160))
    img.save(out)


def _fetch(req, timeout):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 10_000:
        raise RuntimeError("image too small, generator probably returned an error")
    return data


def pollinations(prompt, seed, timeout=180):
    """Free. Anonymous use is rate-limited (about 1 picture per 15s) and some models need a
    free account token: set POLLINATIONS_TOKEN (from auth.pollinations.ai) to raise the limit."""
    token = os.environ.get("POLLINATIONS_TOKEN", "").strip()
    q = f"?width={W}&height={H}&nologo=true&seed={seed}"
    if token:
        q += "&model=flux"
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + q
    headers = {"User-Agent": "channel-pipeline/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _fetch(urllib.request.Request(url, headers=headers), timeout)


def huggingface(prompt, seed, timeout=180):
    """Free tier with a Hugging Face account: set HF_TOKEN (huggingface.co/settings/tokens)."""
    import json as _json
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN not set")
    url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    body = _json.dumps({"inputs": prompt, "parameters": {"width": 1344, "height": 768,
                                                          "seed": seed}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "Accept": "image/png"})
    return _fetch(req, timeout)


PROVIDERS = [("huggingface", huggingface), ("pollinations", pollinations)]
_last_call = [0.0]


def generate_one(prompt, out, seed, log=print):
    """Try each provider with backoff. Pauses between calls so the free limits are respected."""
    errors = []
    providers = [p for p in PROVIDERS if p[0] != "huggingface" or os.environ.get("HF_TOKEN")]
    for name, fn in providers:
        for attempt in range(3):
            wait = 16 - (time.time() - _last_call[0])
            if name == "pollinations" and not os.environ.get("POLLINATIONS_TOKEN") and wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
            try:
                data = fn(prompt, seed)
                tmp = out.with_suffix(".tmp")
                tmp.write_bytes(data)
                Image.open(tmp).convert("RGB").resize((W, H), Image.LANCZOS).save(out)
                tmp.unlink()
                return name
            except Exception as e:  # rate limit, payment required, busy
                msg = str(e)
                errors.append(f"{name}: {msg}")
                if "401" in msg or "403" in msg or "HF_TOKEN" in msg:
                    break
                delay = 20 * (attempt + 1) if ("402" in msg or "429" in msg) else 8 * (attempt + 1)
                log(f"    {name} failed ({msg}); waiting {delay}s")
                time.sleep(delay)
    raise RuntimeError("; ".join(errors[-2:]))


def make_images(scenes, series, folder, generate=False, force=False, log=print):
    folder.mkdir(parents=True, exist_ok=True)
    gen = folder / "_generated"
    gen.mkdir(exist_ok=True)
    st = style_for(series)
    for s in scenes:
        sid = s["id"]
        mine = find_existing(folder, sid)
        if mine:
            s["image"], s["image_source"] = str(mine), "yours"
            continue
        out = gen / f"{sid}.png"
        if s["kind"] == "text":
            text_card(s["card_text"], st, out)
            s["image"], s["image_source"] = str(out), "text card"
            continue
        if out.exists() and not force and not out.name.endswith("_placeholder.png"):
            s["image"], s["image_source"] = str(out), "generated"
            continue
        if generate:
            prompt = f"{s['prompt']} Style: {st['style']}. {NEGATIVE}."
            seed = int(hashlib.md5(sid.encode()).hexdigest()[:6], 16)
            try:
                who = generate_one(prompt, out, seed, log)
                s["image"], s["image_source"] = str(out), "generated"
                log(f"  {sid}: generated ({who})")
            except Exception as e:
                log(f"  {sid}: no picture ({e}); placeholder used, run images again later")
                ph = gen / f"{sid}_placeholder.png"
                placeholder(s, st, ph)
                s["image"], s["image_source"] = str(ph), "placeholder"
        else:
            ph = gen / f"{sid}_placeholder.png"
            placeholder(s, st, ph)
            s["image"], s["image_source"] = str(ph), "placeholder"
    return scenes
