"""Channel voice: find the voice config and the Python that can run Chatterbox."""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_VOICE = HERE / "fajrlight" / "voice.json"


def tts_python():
    """CHATTERBOX_PYTHON from .env wins; else this Python if it has chatterbox installed."""
    p = os.environ.get("CHATTERBOX_PYTHON")
    if p and Path(p).exists():
        return p
    try:
        import importlib.util
        if importlib.util.find_spec("chatterbox"):
            return sys.executable
    except Exception:
        pass
    return None


def available(voice=DEFAULT_VOICE):
    return Path(voice).exists() and tts_python() is not None


def speak(items, words=True, voice=DEFAULT_VOICE, work=None):
    """items: [(text, out_path)]. Writes wavs (and .words.json when words=True)."""
    work = Path(work or Path(items[0][1]).parent)
    jobs = work / "voice_jobs.json"
    jobs.write_text(json.dumps({"voice": str(voice), "words": words,
                                "items": [{"text": t, "out": str(o)} for t, o in items]}))
    subprocess.run([tts_python(), str(HERE / "speak.py"), str(jobs)], check=True)
