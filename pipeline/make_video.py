"""Script in, finished videos out.

    python3 pipeline/make_video.py new channel/scripts/001-three-questions-of-the-grave.md
    # -> videos/001-three-questions-of-the-grave/ with scenes.json and a prompts list
    #    record your voiceover and save it as videos/001-.../voice.wav (or .mp3 / .m4a)

    python3 pipeline/make_video.py images videos/001-... --generate   # free AI images
    python3 pipeline/make_video.py render videos/001-...              # long video + thumbnail
    python3 pipeline/make_video.py short  videos/001-... 4-5          # 9:16 Short from scenes 4-5

Swap any picture by saving your own file as videos/<video>/images/scene_07.png and running
render again. Your files are never overwritten.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from images import make_images  # noqa: E402
from render import (FPS, assign_times, duration, render, run, thumbnail,  # noqa: E402
                    whisper_words)
from images import style_for  # noqa: E402
from scenes import meta as read_meta, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def find_audio(folder, name):
    for ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"):
        p = folder / f"{name}{ext}"
        if p.exists():
            return p
    return None


def load(folder):
    return json.loads((folder / "scenes.json").read_text())


def save(folder, data):
    (folder / "scenes.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))


def cmd_new(a):
    script = Path(a.script)
    md = script.read_text()
    folder = ROOT / "videos" / script.stem
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "images").mkdir(exist_ok=True)
    shutil.copy(script, folder / "script.md")
    data = {"meta": read_meta(md), "scenes": parse(md)}
    save(folder, data)
    lines = [f"# Image prompts: {data['meta']['title']}", "",
             "Generate these anywhere you like (Leonardo, Bing Image Creator, Ideogram...) and save",
             "each as images/<scene>.png, or run `make_video.py images <folder> --generate`.", ""]
    for s in data["scenes"]:
        kind = "TEXT CARD (drawn automatically)" if s["kind"] == "text" else s["prompt"]
        lines += [f"## {s['id']}  ({s['beat']})", f"- Picture: {kind}", f"- Voice: {s['vo']}", ""]
    (folder / "prompts.md").write_text("\n".join(lines))
    words = sum(len(s["vo"].split()) for s in data["scenes"])
    print(f"{folder.relative_to(ROOT)}: {len(data['scenes'])} scenes, {words} spoken words "
          f"(~{words / 150:.1f} min). Next: record voice.wav into that folder.")


def cmd_images(a):
    folder = Path(a.folder)
    data = load(folder)
    make_images(data["scenes"], data["meta"]["series"], folder / "images",
                generate=a.generate, force=a.force)
    save(folder, data)
    src = {}
    for s in data["scenes"]:
        src[s["image_source"]] = src.get(s["image_source"], 0) + 1
    print("pictures:", ", ".join(f"{v} {k}" for k, v in src.items()))


def prepare(folder, a):
    data = load(folder)
    make_images(data["scenes"], data["meta"]["series"], folder / "images", generate=False)
    audio = find_audio(folder, "voice")
    if audio is None:
        if not a.test_voice:
            sys.exit(f"no voice file in {folder}. Record voice.wav, or pass --test-voice for a "
                     "silent test track.")
        words = sum(len(s["vo"].split()) for s in data["scenes"])
        audio = folder / "voice_TEST_SILENT.wav"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
             "anullsrc=r=48000:cl=mono", "-t", f"{words / 2.5:.2f}", str(audio)])
    total = duration(audio)
    spoken = whisper_words(audio)
    assign_times(data["scenes"], total, spoken)
    save(folder, data)
    return data, audio


def cmd_render(a):
    folder = Path(a.folder)
    data, audio = prepare(folder, a)
    amb = find_audio(folder, "ambience")
    out = render(data["scenes"], data["meta"], folder, audio, ambience=amb)
    st = style_for(data["meta"]["series"])
    thumb = folder / "out" / "thumbnail.jpg"
    used = thumbnail(data["scenes"], data["meta"]["thumbnail_text"], st, thumb)
    m = dict(data["meta"])
    m.update({"video": str(out.relative_to(folder)), "thumbnail": "out/thumbnail.jpg",
              "thumbnail_from": used, "altered_or_synthetic": True, "made_for_kids": False,
              "language": "en", "status": "waiting for approval"})
    (folder / "out" / "metadata.json").write_text(json.dumps(m, indent=1, ensure_ascii=False))
    ph = [s["id"] for s in data["scenes"] if s["image_source"] == "placeholder"]
    print(f"done: {out} ({duration(out) / 60:.1f} min), thumbnail.jpg, metadata.json")
    if ph:
        print(f"{len(ph)} scenes still use placeholders: {', '.join(ph)}")


def cmd_short(a):
    folder = Path(a.folder)
    data, audio = prepare(folder, a)
    lo, _, hi = a.scenes.partition("-")
    ids = {f"scene_{i:02d}" for i in range(int(lo), int(hi or lo) + 1)}
    secs = sum(s["frames"] for s in data["scenes"] if s["id"] in ids) / FPS
    if secs > 60:
        print(f"warning: {secs:.0f}s is over 60s; Shorts work best under 60s")
    out = render(data["scenes"], data["meta"], folder, audio, vertical=True, only=ids)
    print(f"done: {out} ({secs:.0f}s)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("script"); n.set_defaults(fn=cmd_new)
    i = sub.add_parser("images"); i.add_argument("folder")
    i.add_argument("--generate", action="store_true", help="use the free AI generator")
    i.add_argument("--force", action="store_true", help="regenerate AI pictures already made")
    i.set_defaults(fn=cmd_images)
    r = sub.add_parser("render"); r.add_argument("folder")
    r.add_argument("--test-voice", action="store_true"); r.set_defaults(fn=cmd_render)
    s = sub.add_parser("short"); s.add_argument("folder"); s.add_argument("scenes")
    s.add_argument("--test-voice", action="store_true"); s.set_defaults(fn=cmd_short)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
