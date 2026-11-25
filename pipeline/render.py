"""Sync scenes to the voiceover and render the videos with ffmpeg.

Timing: if faster-whisper is installed (pip install faster-whisper, free, runs offline) the
voiceover is transcribed and every scene starts on its first spoken word. Without it, scenes get
time in proportion to their word count, which is close enough for a first review.
"""
import json
import math
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from images import FONT, FONT_BOLD, font, style_for

FPS = 30
MIN_SCENE = 2.5      # seconds for a picture with no words over it
FADE = 0.25


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(map(str, cmd))[:600]}\n{p.stderr[-1500:]}")
    return p


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
               "default=nw=1:nk=1", str(path)]).stdout
    return float(out.strip())


def words(t):
    return re.findall(r"[\w']+", t.lower())


# ---------------------------------------------------------------- timing

def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def whisper_words(audio, log=print, srt_out=None):
    """Word timings from the voiceover. Also writes an .srt that /yt-edit and /yt-chapters read."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    log("  transcribing voiceover with faster-whisper (offline)...")
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs = list(model.transcribe(str(audio), word_timestamps=True)[0])
    if srt_out:
        Path(srt_out).write_text("".join(
            f"{i}\n{srt_time(s.start)} --> {srt_time(s.end)}\n{s.text.strip()}\n\n"
            for i, s in enumerate(segs, 1)), encoding="utf-8")
    return [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]


def assign_times(scenes, total, spoken=None):
    counts = [len(words(s["vo"])) for s in scenes]
    if spoken:
        # walk the script words against the transcript, scene by scene
        starts, i = [], 0
        for c in counts:
            starts.append(spoken[min(i, len(spoken) - 1)][1] if c else None)
            i += c
        starts[0] = 0.0
        for k in range(len(starts)):
            if starts[k] is None:
                starts[k] = starts[k - 1] + MIN_SCENE
        bounds = starts + [total]
    else:
        weight = [max(c, MIN_SCENE * 2.5) for c in counts]   # ~2.5 words per second
        scale = total / sum(weight)
        bounds, t = [0.0], 0.0
        for w in weight:
            t += w * scale
            bounds.append(t)
        bounds[-1] = total
    # snap to frames so clips add up exactly to the audio
    for k, s in enumerate(scenes):
        a, b = round(bounds[k] * FPS), round(bounds[k + 1] * FPS)
        s["start"], s["frames"] = a / FPS, max(b - a, int(FPS))
    return scenes


def caption_chunks(scene, spoken=None, max_words=7):
    w = scene["vo"].split()
    if not w:
        return []
    chunks = [" ".join(w[i:i + max_words]) for i in range(0, len(w), max_words)]
    dur = scene["frames"] / FPS
    sizes = [len(c.split()) for c in chunks]
    out, t = [], 0.0
    for c, n in zip(chunks, sizes):
        d = dur * n / sum(sizes)
        out.append((c, t, t + d))
        t += d
    return out


# ---------------------------------------------------------------- overlays

def overlay_png(path, size, draw_fn):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), img)
    img.save(path)


def caption_png(text, path, size, vertical):
    W, H = size
    f = font(FONT_BOLD, 64 if vertical else 52)
    lines = textwrap.wrap(text, 22 if vertical else 42)

    def draw(d, img):
        lh = int(f.size * 1.3)
        y = int(H * (0.62 if vertical else 0.80)) - (len(lines) - 1) * lh // 2
        for line in lines:
            w = d.textlength(line, font=f)
            d.text(((W - w) / 2, y), line, font=f, fill=(255, 255, 255),
                   stroke_width=5, stroke_fill=(0, 0, 0))
            y += lh
    overlay_png(path, size, draw)


def card_png(text, path, size, st, vertical):
    W, H = size
    f = font(FONT_BOLD, 40 if vertical else 34)

    def draw(d, img):
        label = "SOURCE  " + text
        w = d.textlength(label, font=f)
        x = (W - w) / 2 if vertical else 60
        y = int(H * 0.12) if vertical else 50
        d.rounded_rectangle([x - 24, y - 16, x + w + 24, y + f.size + 20], 14,
                            fill=(0, 0, 0, 170), outline=st["accent"], width=3)
        d.text((x, y), label, font=f, fill=st["accent"])
    overlay_png(path, size, draw)


def sting_png(text, path, size, st):
    W, H = size
    f = font(FONT_BOLD, 96)

    def draw(d, img):
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, 140))
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, H / 2 - 60), text, font=f, fill=st["accent"])
        d.line([(W / 2 - w / 2, H / 2 + 60), (W / 2 + w / 2, H / 2 + 60)], fill=st["accent"], width=4)
    overlay_png(path, size, draw)


# ---------------------------------------------------------------- clips

def motion(k, frames, vertical):
    """Slow Ken Burns move. Alternates zoom in / zoom out / pan so it never feels repeated."""
    z = 0.12 / max(frames, 1)
    out = "1080x1920" if vertical else "1920x1080"
    pre = ("crop=ih*9/16:ih,scale=2160:3840" if vertical else "scale=3840:2160")
    moves = [
        f"zoompan=z='min(1+{z}*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        f"zoompan=z='max(1.12-{z}*on,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        f"zoompan=z='1.1':x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)'",
        f"zoompan=z='1.1':x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)'",
    ]
    return f"{pre},{moves[k % 4]}:d={frames}:s={out}:fps={FPS}"


def render_clip(k, s, st, work, vertical, spoken=None):
    size = (1080, 1920) if vertical else (1920, 1080)
    frames, dur = s["frames"], s["frames"] / FPS
    if str(s["image"]).lower().endswith((".mp4", ".mov", ".webm")):
        # a finished clip (3D shot, motion graphic): no camera move, just fit and loop/trim it
        W, H = size
        inputs = ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", s["image"]]
        chain = (f"[0:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H},setsar=1,format=yuv420p[v0]")
    else:
        inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", s["image"]]
        chain = f"[0:v]{motion(k, frames, vertical)},setsar=1,format=yuv420p[v0]"
    filters, last, n = [chain], "v0", 1

    def add(png, a, b):
        nonlocal last, n
        inputs.extend(["-i", str(png)])
        filters.append(f"[{last}][{n}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{n}]")
        last, n = f"v{n}", n + 1

    tag = "v" if vertical else "h"
    if s.get("sting") and not vertical:
        p = work / f"{s['id']}_{tag}_sting.png"
        sting_png(s["sting"], p, size, st)
        add(p, 0, min(2.5, dur))
    for j, card in enumerate(s["cards"][:2]):
        p = work / f"{s['id']}_{tag}_card{j}.png"
        card_png(card, p, size, st, vertical)
        add(p, 0.4 + j * dur / 2, dur)
    for j, (text, a, b) in enumerate(caption_chunks(s)):
        p = work / f"{s['id']}_{tag}_cap{j}.png"
        caption_png(text, p, size, vertical)
        add(p, a, b)
    fade = f"[{last}]fade=t=in:st=0:d={FADE},fade=t=out:st={max(dur - FADE, 0):.3f}:d={FADE}[out]"
    filters.append(fade)
    out = work / f"{s['id']}_{tag}.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[out]", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", str(out)])
    return out


def concat(clips, audio, start, length, out, ambience=None):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(audio)]
    if ambience:
        cmd += ["-stream_loop", "-1", "-i", str(ambience), "-filter_complex",
                "[2:a]volume=0.08[amb];[1:a][amb]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    run(cmd)
    lst.unlink()


def thumbnail(scenes, text, st, out):
    pick = next((s for s in scenes if s.get("image_source") in ("yours", "generated")), None) \
        or next(s for s in scenes if s["kind"] == "image")
    img = Image.open(pick["image"]).convert("RGB").resize((1280, 720))
    img = ImageEnhance.Brightness(img).enhance(0.6)
    d = ImageDraw.Draw(img)
    f = font(FONT_BOLD, 120)
    lines = textwrap.wrap(text.upper() or "WATCH", 12)
    y = 720 - 80 - len(lines) * 135
    for line in lines:
        d.text((60, y), line, font=f, fill=(255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0))
        y += 135
    d.rectangle([0, 700, 1280, 720], fill=st["accent"])
    img.save(out, quality=92)
    return pick["id"]


def render(scenes, meta, folder, audio, vertical=False, only=None, ambience=None, log=print):
    st = style_for(meta.get("series", ""))
    work = folder / "_work"
    work.mkdir(exist_ok=True)
    outdir = folder / "out"
    outdir.mkdir(exist_ok=True)
    chosen = [s for s in scenes if only is None or s["id"] in only]
    clips = []
    for k, s in enumerate(chosen):
        log(f"  rendering {s['id']} ({s['frames'] / FPS:.1f}s, {s['image_source']})")
        clips.append(render_clip(k, s, st, work, vertical))
    start = chosen[0]["start"]
    length = sum(s["frames"] for s in chosen) / FPS
    if vertical:
        name = f"short_{chosen[0]['id'][6:]}-{chosen[-1]['id'][6:]}.mp4"
    else:
        name = "long.mp4"
    out = outdir / name
    concat(clips, audio, start, length, out, ambience)
    return out
