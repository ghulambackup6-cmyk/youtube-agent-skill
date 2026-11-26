# Video pipeline

Turns a script from `channel/scripts/` into a finished long video, vertical Shorts, a thumbnail
and the upload details. Free tools only: Python, Pillow, ffmpeg, and optionally a free AI image
generator and an offline speech-to-text model.

## One-time setup (each laptop)

1. Install **Python 3.10+** and **ffmpeg** (Windows: `winget install Gyan.FFmpeg`, Mac:
   `brew install ffmpeg`).
2. In the repo folder: `pip install -r pipeline/requirements.txt`
3. Optional, recommended: `pip install faster-whisper "av<14"`. It listens to your voiceover (offline,
   free) so every picture changes exactly when you start talking about it, and it makes the
   captions match your words. Without it, timing is estimated from word counts.

## Free picture generators

The free Pollinations service now limits anonymous use, so the pipeline waits about 16 seconds
between pictures and retries when it is busy. For faster, more reliable pictures, add a free
token. Create a file called `.env` in the repo folder (it is never uploaded to GitHub):

```
HF_TOKEN=hf_xxxxxxxx            # free: huggingface.co > Settings > Access Tokens > "Read"
POLLINATIONS_TOKEN=xxxxxxxx     # optional, free: auth.pollinations.ai
```

With `HF_TOKEN` set, Hugging Face (FLUX.1-schnell) is tried first and Pollinations is the backup.
Running `images --generate` again only redoes the scenes that are still placeholders.

## Making a video

```bash
# 1. Script -> scene list. Creates videos/001-.../ with scenes.json and prompts.md
python3 pipeline/make_video.py new channel/scripts/001-three-questions-of-the-grave.md

# 2. Record your voiceover from the script. Save it in that folder as voice.wav
#    (.mp3 / .m4a also work). Optional: ambience.mp3 for quiet background sound.

# 3. Pictures. Either generate them free:
python3 pipeline/make_video.py images videos/001-three-questions-of-the-grave --generate
#    or make them yourself from prompts.md and save as images/scene_01.png, scene_02.png ...

# 4. Render the long video + thumbnail + metadata.json
python3 pipeline/make_video.py render videos/001-three-questions-of-the-grave

# 5. Shorts: pick scenes from the scene list (scenes 4 to 5 here)
python3 pipeline/make_video.py short videos/001-three-questions-of-the-grave 4-5
```

Everything lands in `videos/<video>/out/`: `long.mp4`, `short_XX-YY.mp4`, `thumbnail.jpg`,
`metadata.json` (title, description, AI-content flag, language).

## Changing pictures (your part, and what makes it count as human-made)

- Don't like a picture? Save your own as `images/scene_07.png` and run `render` again. Your own
  files always win and are never overwritten.
- Want the AI to try again? Delete `images/_generated/scene_07.png` and run `images --generate`.
- Scenes whose ON SCREEN line has words in quotes become clean text cards automatically, since
  AI generators misspell text.
- Any scene that mentions the Prophet ﷺ or a Companion gets this added to the prompt: the face is
  fully covered by a soft white light. **Always check those scenes yourself before approving.**

## What each picture gets automatically

- Slow camera movement (zoom in, zoom out, pan left, pan right, in rotation).
- Captions from your words, big and outlined.
- A gold **SOURCE** card whenever the script cites an ayah or hadith.
- The series title card ("Unseen Explained") where the script has a SERIES STING.
- A short fade between pictures.

## Test without a voiceover

`render --test-voice` uses a silent track at about 2.5 words a second, so you can check the
pictures and timing before recording.

## Cleaning your voiceover and chapters

```bash
python3 pipeline/make_video.py clean videos/001-...      # /yt-edit: cuts retakes, "um", long silences
python3 pipeline/make_video.py chapters videos/001-...   # /yt-chapters from the final voice
```

`clean` needs faster-whisper. It keeps pauses up to 1.2 seconds (`--floor 1.5` to keep more),
writes `voice_clean.wav`, and render uses it automatically. Delete it to go back.

3D shots and other clips: save them as `images/scene_XX.mp4`. See [SKILLS.md](SKILLS.md) for
which skill is used at each stage.

## Files

| File | Job |
|---|---|
| `scenes.py` | Reads the script, pairs each ON SCREEN with its voiceover and source cards |
| `images.py` | Your images, free AI images, or placeholders; draws text cards |
| `render.py` | Timing, captions, source cards, camera moves, ffmpeg render, thumbnail |
| `make_video.py` | The commands above |

## Approving a video (step 3)

```bash
python3 pipeline/review.py serve videos/001-three-questions-of-the-grave
```

It prints two links: one for the laptop and one for your phone (same Wi-Fi). The page shows
the full video, every scene with its picture, voiceover and sources, the Shorts, and the
upload details.

- For each scene: **Approve**, **Redo** (write a note like "darker, no people"), or **I'll
  replace it** (then save your own `images/scene_XX.png`).
- Scenes that may show a Prophet or Companion are flagged in orange. Check the face is covered.
- Edit the title, thumbnail text and description, and pick the publish time.
- Press **Save decisions**. It saves `review.json` into the video folder.

Then:

```bash
python3 pipeline/review.py apply videos/001-three-questions-of-the-grave
```

Redo scenes get new AI pictures with your note added to the prompt. Render again, review again.
When every scene is approved and a publish time is set, `approval.json` says
`"ready_to_publish": true`, and the publishing step (step 4) will only upload videos in that state.
