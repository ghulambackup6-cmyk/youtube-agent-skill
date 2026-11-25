"""Turn a channel script (channel/scripts/*.md) into a scene list.

A scene is one picture on screen and the voiceover spoken over it. The script format is in
channel/script-format.md: VO lines, [ON SCREEN: ...] lines, [SOURCE CARD: ...] lines and an
optional [SERIES STING ...] line, inside the first ``` block under "## Script".

Pairing rule, which matches how the scripts are written:
- VO followed by ON SCREEN: that picture goes with that VO.
- ON SCREEN with no VO waiting: the picture comes first, and the next VO block is spoken over it.
"""
import json
import re
import sys
from pathlib import Path

TAG = re.compile(r"^\[(ON SCREEN|SOURCE CARD|SERIES STING[^:\]]*)\s*:?\s*(.*?)\]\s*$")
HEADER = re.compile(r"^\[(\d+:\d+)?\s*([A-Z][^\]]*)\]\s*$")
TITLE = re.compile(r"^#\s+(?:\d+\.\s*)?(.+)$", re.M)
SERIES = re.compile(r"\*\*Series:\*\*\s*(.+)")

# Words that mean a Prophet or Companion may be in the picture. Those prompts get the face rule.
SACRED = re.compile(r"\b(prophet|messenger|companion|sahab|sahabi|abu bakr|umar|uthman|ali ibn|"
                    r"bilal|khadijah|aishah|figure whose face)\b|ﷺ", re.I)
FACE_RULE = ("Any Prophet or Companion is shown only as a robed figure whose entire face is "
             "covered by a soft glowing white light; no facial features visible.")


def script_block(md):
    part = md.split("## Script", 1)[-1]
    m = re.search(r"```[a-z]*\n(.*?)```", part, re.S)
    if not m:
        sys.exit("no ``` script block found under '## Script'")
    return m.group(1)


def parse(md):
    lines = script_block(md).splitlines()
    scenes, pending, open_scene = [], [], None
    vo, beat, sting = None, "", None

    def flush_vo():
        nonlocal vo
        if vo:
            pending.append(vo)
        vo = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_vo()
            continue
        tag = TAG.match(line.strip())
        if tag:
            kind, val = tag.group(1), tag.group(2).strip()
            if kind == "SOURCE CARD":
                if vo is None and pending:
                    pending[-1]["cards"].append(val)
                elif vo is not None:
                    vo["cards"].append(val)
                elif scenes:
                    scenes[-1]["cards"].append(val)
                continue
            flush_vo()
            if kind.startswith("SERIES STING"):
                sting = val.strip('"') or kind
                continue
            # ON SCREEN
            if open_scene is not None and open_scene["_vo_blocks"] == 0 and pending:
                # picture came first, its VO is the first pending block
                b = pending.pop(0)
                open_scene["vo"] = b["text"]
                open_scene["cards"] += b["cards"]
                open_scene["_vo_blocks"] = 1
            if pending:
                text = " ".join(b["text"] for b in pending)
                cards = [c for b in pending for c in b["cards"]]
                pending.clear()
                scenes.append(new_scene(val, text, cards, beat, sting))
                sting = None
                open_scene = None
            else:
                s = new_scene(val, "", [], beat, sting)
                sting = None
                scenes.append(s)
                open_scene = s
            continue
        head = HEADER.match(line.strip())
        if head and not line.strip().startswith("[ON"):
            flush_vo()
            # VO left over at the end of a beat is still spoken over that beat's last picture
            if pending and scenes and (open_scene is None or open_scene["_vo_blocks"]):
                for b in pending:
                    scenes[-1]["vo"] = (scenes[-1]["vo"] + " " + b["text"]).strip()
                    scenes[-1]["cards"] += b["cards"]
                pending.clear()
            beat = head.group(2).strip()
            continue
        if line.strip().startswith("VO:"):
            flush_vo()
            vo = {"text": line.strip()[3:].strip(), "cards": []}
        elif vo is not None:
            vo["text"] += " " + line.strip()
    flush_vo()
    if pending:
        if open_scene is not None and open_scene["_vo_blocks"] == 0:
            b = pending.pop(0)
            open_scene["vo"], open_scene["cards"] = b["text"], open_scene["cards"] + b["cards"]
        for b in pending:  # VO with no picture after it: hold the last picture
            scenes[-1]["vo"] = (scenes[-1]["vo"] + " " + b["text"]).strip()
            scenes[-1]["cards"] += b["cards"]
    for i, s in enumerate(scenes, 1):
        s.pop("_vo_blocks", None)
        s["id"] = f"scene_{i:02d}"
    return scenes


def new_scene(visual, vo, cards, beat, sting):
    # Pictures that must show words are rendered as text cards: AI image models misspell text.
    quoted = re.search(r'"([^"]{2,})"?', visual)
    kind = "text" if visual.lower().startswith("text:") or quoted else "image"
    card_text = quoted.group(1).strip() if quoted else visual.split(":", 1)[-1].strip()
    prompt = visual
    if kind == "image" and SACRED.search(visual + " " + vo):
        prompt = f"{visual} {FACE_RULE}"
    return {"beat": beat, "visual": visual, "kind": kind, "prompt": prompt, "vo": vo,
            "card_text": card_text if kind == "text" else "",
            "cards": cards, "sting": sting, "_vo_blocks": 1 if vo else 0}


def meta(md):
    t = TITLE.search(md)
    s = SERIES.search(md)
    desc = ""
    m = re.search(r"## Description.*?```[a-z]*\n(.*?)```", md, re.S)
    if m:
        desc = m.group(1).strip()
    thumb = re.search(r'Text, 3 words.*?\*\*"?([^*"]+)"?\*\*', md, re.S)
    return {"title": t.group(1).strip() if t else "Untitled",
            "series": s.group(1).strip() if s else "",
            "description": desc,
            "thumbnail_text": thumb.group(1).strip() if thumb else ""}


if __name__ == "__main__":
    md = Path(sys.argv[1]).read_text()
    print(json.dumps({"meta": meta(md), "scenes": parse(md)}, indent=1, ensure_ascii=False))
