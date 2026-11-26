"""Build a finished vertical Short from a short script (channel/scripts/*-short-*.json).

    python3 pipeline/motion/make_short.py channel/scripts/002-short-3-questions-grave.json

Voice, in order of preference:
  1. Your recording, one file per line: videos/<id>/voice/line_01.wav, line_02.wav ...
     (record each line separately; easiest to retake one line)
  2. The channel voice, cloned for free with Chatterbox (pipeline/voice/fajrlight/). Needs
     chatterbox-tts installed in this Python, or CHATTERBOX_PYTHON=<path to that python> in .env
  3. ElevenLabs, if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are in .env
  4. A robotic guide voice (espeak-ng) so you can judge pacing and visuals. Never publish it.

The timing of every shot, caption word and sound effect comes from the voice lines, so when
you swap in your own recording everything re-times itself.
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import voice as channel_voice  # noqa: E402
GAP, SCENE_GAP, TAIL = 0.25, 0.55, 1.2
SR = 48000

env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-1200:]}")
    return p.stdout


def dur(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                      "default=nw=1:nk=1", str(path)]).strip())


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(SR),
         "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                "silenceremove=start_periods=1:start_threshold=-45dB,areverse", str(dst)])


def eleven(text, dst):
    key, vid = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_VOICE_ID")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                         "voice_settings": {"stability": .45, "similarity_boost": .8,
                                            "style": .35}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        Path(dst).write_bytes(r.read())


def guide_voice(text, dst):
    tmp = Path(dst).with_suffix(".raw.wav")
    run(["espeak-ng", "-v", "en-us+m3", "-s", "138", "-p", "32", "-w", str(tmp), text])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af",
         "aecho=0.6:0.5:40:0.12,lowpass=f=6000", str(dst)])
    tmp.unlink()


def voice_lines(spec, folder):
    vdir = folder / "voice"
    vdir.mkdir(parents=True, exist_ok=True)
    work = folder / "_work"
    work.mkdir(exist_ok=True)
    kinds, out = [], []
    clone = channel_voice.available() and not os.environ.get("NO_CLONE")
    if clone:   # one batch so the model loads once
        todo = [(L["text"], work / f"cloned_{i:02d}.wav") for i, L in enumerate(spec["lines"], 1)
                if not any((vdir / f"line_{i:02d}{e}").exists() for e in (".wav", ".mp3", ".m4a"))]
        if todo:
            channel_voice.speak(todo, words=True, work=work)
    for i, L in enumerate(spec["lines"], 1):
        mine = next((vdir / f"line_{i:02d}{e}" for e in (".wav", ".mp3", ".m4a")
                     if (vdir / f"line_{i:02d}{e}").exists()), None)
        dst = work / f"line_{i:02d}.wav"
        cloned = work / f"cloned_{i:02d}.wav"
        if mine:
            to_wav(mine, dst); kinds.append("your recording")
        elif clone and cloned.exists():
            to_wav(cloned, dst); kinds.append("Fajrlight voice (cloned)")
            wj = cloned.with_suffix(".words.json")
            if wj.exists():
                L["_spoken"] = json.loads(wj.read_text())
        elif os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
            mp3 = dst.with_suffix(".mp3"); eleven(L["text"], mp3); to_wav(mp3, dst)
            kinds.append("ElevenLabs")
        else:
            raw = dst.with_suffix(".g.wav"); guide_voice(L["text"], raw); to_wav(raw, dst)
            kinds.append("GUIDE VOICE (robotic, for timing only)")
        out.append(dst)
    kind = next((k for k in kinds if k.startswith("GUIDE")), kinds[0])
    return out, kind


def caption_times(cap, start, d, spoken=None):
    """Word times for the captions: from the transcript when we have one, else by word length."""
    if spoken and len(spoken) == len(cap):
        return [{"w": x, "s": round(start + w["s"], 3), "e": round(start + w["e"], 3)}
                for x, w in zip(cap, spoken)]
    s0, s1 = (spoken[0]["s"], spoken[-1]["e"]) if spoken else (0, d)
    weights = [len(x) + 2 for x in cap]
    s, words = start + s0, []
    for x, k in zip(cap, weights):
        e = s + (s1 - s0) * k / sum(weights)
        words.append({"w": x, "s": round(s, 3), "e": round(e, 3)})
        s = e
    return words


def build_timeline(spec, wavs):
    t, lines = 0.6, []
    for i, (L, w) in enumerate(zip(spec["lines"], wavs)):
        d = dur(w)
        if i and spec["lines"][i - 1]["scene"] != L["scene"]:
            t += SCENE_GAP - GAP
        cap = L.get("caption", L["text"]).split()
        words = caption_times(cap, t, d, L.pop("_spoken", None))
        lines.append({**L, "start": round(t, 3), "end": round(t + d + GAP, 3), "voice_at": t,
                      "words": words})
        t += d + GAP
    lines[-1]["end"] = round(t + TAIL, 3)
    # shots: consecutive lines with the same scene share one camera move
    i = 0
    while i < len(lines):
        j = i
        while j + 1 < len(lines) and lines[j + 1]["scene"] == lines[i]["scene"]:
            j += 1
        for k in range(i, j + 1):
            lines[k]["shotStart"], lines[k]["shotEnd"] = lines[i]["start"], lines[j]["end"]
        for k in range(i, j):
            lines[k]["end"] = lines[k + 1]["start"]
        i = j + 1
    for k in range(len(lines) - 1):
        lines[k]["end"] = lines[k + 1]["start"]
    return {"lines": lines, "total": lines[-1]["end"]}


# ---------------------------------------------------------------- sound design

def sfx_track(tl, work):
    """Everything synthesised with ffmpeg: no licensed audio needed."""
    T = tl["total"]
    parts = []

    def make(name, expr, d):
        p = work / f"sfx_{name}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", expr, "-t", f"{d}", "-ar", str(SR),
             "-ac", "1", str(p)])
        return p

    wind = make("wind", f"anoisesrc=c=brown:a=0.5:d={T},lowpass=f=420,highpass=f=60,"
                        f"volume='0.55+0.25*sin(2*PI*t/7)':eval=frame", T)
    drone = make("drone", f"aevalsrc='0.25*sin(2*PI*55*t)+0.18*sin(2*PI*82.4*t)+"
                          f"0.08*sin(2*PI*110*t)':d={T},volume='0.6+0.4*sin(2*PI*t/11)':eval=frame,"
                          f"lowpass=f=300", T)
    step = make("step", "anoisesrc=c=pink:a=0.9:d=0.09,lowpass=f=900,afade=t=out:st=0.01:d=0.08", 0.09)
    whoosh = make("whoosh", "anoisesrc=c=white:a=0.6:d=0.9,bandpass=f=2600:w=1800,"
                            "afade=t=in:d=0.45,afade=t=out:st=0.45:d=0.45", 0.9)
    boom = make("boom", "aevalsrc='0.9*sin(2*PI*48*t)*exp(-4*t)':d=1.4,lowpass=f=160", 1.4)
    chime = make("chime", "aevalsrc='0.25*(sin(2*PI*880*t)+sin(2*PI*1318.5*t)+sin(2*PI*1760*t))"
                          "*exp(-1.6*t)':d=2.5", 2.5)
    heart = make("heart", "aevalsrc='0.9*sin(2*PI*52*t)*exp(-18*t)+0.7*sin(2*PI*48*(t-0.22))"
                          "*exp(-18*(t-0.22))*gte(t,0.22)':d=0.8,lowpass=f=140", 0.8)
    flip = make("flip", "anoisesrc=c=white:a=0.5:d=0.25,highpass=f=1500,afade=t=out:st=0.02:d=0.2", 0.25)

    events = []
    prev = None
    for L in tl["lines"]:
        if L["scene"] != prev:
            events.append((whoosh, max(L["start"] - .35, 0), .35))
            if L["scene"] in ("angels", "flood"):
                events.append((chime, L["start"] + .2, .6))
            if L["scene"].startswith("card"):
                events.append((flip, L["start"] + .25, .7)); events.append((boom, L["start"] + .25, .5))
            if L["scene"] == "mourners":
                for k in range(int((L["shotEnd"] - L["shotStart"]) / .55)):
                    events.append((step, L["start"] + k * .55, .5 * (1 - k / 14)))
            if L["scene"] == "closing":
                d = L["shotEnd"] - L["shotStart"]
                for k in range(int(d / .84)):
                    events.append((heart, L["start"] + k * .84, .9))
            if L["scene"] == "graveyard" and L is tl["lines"][0]:
                events.append((boom, 0.05, .8))
        prev = L["scene"]

    inputs = ["-i", str(wind), "-i", str(drone)]
    filt = ["[0:a]volume=0.35[w]", "[1:a]volume=0.30[d]"]
    labels = ["[w]", "[d]"]
    for n, (src, at, vol) in enumerate(events, 2):
        inputs += ["-i", str(src)]
        filt.append(f"[{n}:a]adelay={int(at * 1000)}|{int(at * 1000)},volume={vol:.2f}[e{n}]")
        labels.append(f"[e{n}]")
    filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[mix]")
    out = work / "sfx.wav"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
         "-map", "[mix]", "-t", f"{T}", "-ac", "1", "-ar", str(SR), str(out)])
    return out


def voice_track(tl, wavs, work):
    inputs, filt, labels = [], [], []
    for n, (L, w) in enumerate(zip(tl["lines"], wavs)):
        inputs += ["-i", str(w)]
        ms = int(L["voice_at"] * 1000)
        filt.append(f"[{n}:a]adelay={ms}|{ms}[v{n}]"); labels.append(f"[v{n}]")
    filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[v]")
    out = work / "voice_track.wav"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[v]",
         "-t", f"{tl['total']}", "-ac", "1", "-ar", str(SR), str(out)])
    return out


def mix(voice, sfx, out):
    # voice up front, sound bed ducked under it, mastered to about -14 LUFS for phones
    run(["ffmpeg", "-y", "-v", "error", "-i", str(voice), "-i", str(sfx), "-filter_complex",
         "[1:a][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[bed];"
         "[0:a]acompressor=threshold=0.1:ratio=3,volume=1.6[v];"
         "[v][bed]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]",
         "-map", "[a]", "-ar", str(SR), str(out)])


def main():
    spec_path = Path(sys.argv[1])
    spec = json.loads(spec_path.read_text())
    folder = ROOT / "videos" / spec["id"]
    work = folder / "_work"
    work.mkdir(parents=True, exist_ok=True)
    (folder / "out").mkdir(exist_ok=True)
    fps = int(os.environ.get("FPS", "30"))

    wavs, kind = voice_lines(spec, folder)
    tl = build_timeline(spec, wavs)
    (work / "timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False))
    print(f"voice: {kind}; length {tl['total']:.1f}s, {len(tl['lines'])} lines")

    audio = work / "audio.wav"
    mix(voice_track(tl, wavs, work), sfx_track(tl, work), audio)

    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    node_path = run(["npm", "root", "-g"]).strip()
    subprocess.run(["node", str(HERE / "frames.js"), str(work / "timeline.json"), str(frames),
                    str(fps)], check=True, env={**os.environ, "NODE_PATH": node_path})
    name = "short_guide_voice.mp4" if kind.startswith("GUIDE") else "short.mp4"
    out = folder / "out" / name
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", str(frames / "f%05d.jpg"),
         "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", str(out)])
    meta = {"title": spec["title"], "series": spec["series"], "voice": kind,
            "description": spec["title"] + "\n\nSources\n" + "\n".join(spec["sources"]) +
            "\n\nVisuals are animated illustrations. Angels are shown only as light.",
            "altered_or_synthetic": True, "language": "en"}
    (folder / "out" / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"done: {out} ({dur(out):.1f}s)")


if __name__ == "__main__":
    main()
