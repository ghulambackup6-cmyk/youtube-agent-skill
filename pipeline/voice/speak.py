"""Speak text in the channel voice with Chatterbox TTS (MIT licence, free, runs locally).

Run with the Python that has chatterbox-tts installed:
    python pipeline/voice/speak.py jobs.json
jobs.json = {"voice": "pipeline/voice/fajrlight/voice.json",
             "items": [{"text": "...", "out": "path/line_01.wav"}, ...],
             "words": true}
For each item it writes out.wav, and with "words" also out.words.json (word timings from
faster-whisper, used for karaoke captions). Items whose text and voice settings did not change
since last time are skipped, so re-renders are fast.
"""
import hashlib, json, re, sys
from pathlib import Path

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen " \
       "fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num(n):
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000: return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " and " + num(n % 100))
    return str(n)


def spoken(text):
    """What the narrator should actually say: small numbers as words, no symbols."""
    text = re.sub(r"\b(\d{1,3})\b", lambda m: num(int(m.group(1))), text)
    return text.replace("ﷺ", "peace be upon him").replace("…", "...").strip()


def chunks(text, limit=280):
    """Chatterbox is best under ~300 characters; split long paragraphs at sentence ends."""
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(s) > limit:
            parts.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    return parts + ([cur] if cur else [])


def main(jobs_path):
    jobs = json.loads(Path(jobs_path).read_text())
    vpath = Path(jobs["voice"]); v = json.loads(vpath.read_text())
    ref = str(vpath.parent / v["reference"])
    todo = []
    for it in jobs["items"]:
        out = Path(it["out"]); text = spoken(it["text"])
        key = hashlib.sha1(json.dumps([text, v, Path(ref).stat().st_size]).encode()).hexdigest()
        stamp = out.with_suffix(".key")
        if out.exists() and stamp.exists() and stamp.read_text() == key:
            continue
        todo.append((out, text, key, stamp))
    import torch, torchaudio as ta
    if todo:
        speak_all(todo, v, ref)
    if jobs.get("words"):
        need = [(Path(it["out"]), spoken(it["text"])) for it in jobs["items"]
                if not Path(it["out"]).with_suffix(".words.json").exists()
                or any(Path(it["out"]) == o for o, *_ in todo)]
        if need:
            align(need)
    print("voice: done")


def align(items):
    import torchaudio as ta
    from faster_whisper import WhisperModel
    wm = WhisperModel("small.en", device="cpu", compute_type="int8")
    for out, text in items:
        wav, sr = ta.load(str(out))
        audio = ta.functional.resample(wav.mean(0), sr, 16000).numpy()
        segs, _ = wm.transcribe(audio, word_timestamps=True, language="en", initial_prompt=text)
        words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
                 for s in segs for w in s.words]
        out.with_suffix(".words.json").write_text(json.dumps(words))


def speak_all(todo, v, ref):
    import torch, torchaudio as ta
    from chatterbox.tts import ChatterboxTTS
    dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    model = ChatterboxTTS.from_pretrained(device=dev)
    for n, (out, text, key, stamp) in enumerate(todo, 1):
        print(f"voice {n}/{len(todo)} [{dev}]: {text[:60]}", flush=True)
        torch.manual_seed(v.get("seed", 7))
        pieces = []
        for c in chunks(text):
            w = model.generate(c, audio_prompt_path=ref, exaggeration=v["exaggeration"],
                               cfg_weight=v["cfg_weight"], temperature=v.get("temperature", 0.8))
            pieces += [w, torch.zeros(1, int(model.sr * 0.3))]
        audio = torch.cat(pieces[:-1], dim=1)
        loud = (audio.abs() > 0.006).nonzero()
        if len(loud):   # trim silence so word timings line up with the file
            a, b = int(loud[0, 1]), int(loud[-1, 1])
            audio = audio[:, max(0, a - int(.02 * model.sr)): b + int(.08 * model.sr)]
        out.parent.mkdir(parents=True, exist_ok=True)
        ta.save(str(out), audio, model.sr)
        stamp.write_text(key)


if __name__ == "__main__":
    main(sys.argv[1])
