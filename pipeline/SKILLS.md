# Which skill runs where

Every video goes through the same line. This is where each skill sits.

| Stage | Skill | How it is used |
|---|---|---|
| Pick topics (Sunday) | `/yt-viral` | Finds what is working in Islamic history, horror and "explained" channels, ranked by how far each video beat its own channel (`swipe.py`). Feeds next week's 3 topics. |
| Plan the week | `/yt-plan` | Turns the topics into the Mon / Wed / Sat calendar (`channel/calendar/`). |
| Write | `/yt-script` | Hooks scored with `hookscore.py`, beats with ON SCREEN lines, plus the sourcing rules in `channel/script-format.md`. |
| Scenes | `pipeline/scenes.py` | Splits the script into scenes. |
| 3D shots | `/3d-animator` | Series intro stings (one per series) and a few hero shots per video, e.g. the three question cards flipping. Each is rendered with the skill's kit as an .mp4 and dropped in as `images/scene_XX.mp4`; the pipeline loops or trims it to the scene length. |
| Pictures | `pipeline/images.py` | Free AI pictures for every other scene, your own images override. |
| Motion | `/motion-design` | Timing and easing rules for the camera moves, caption pop-ins, source cards and transitions in `render.py` (ease in-out moves, no linear motion, 2-4 frame staggers). |
| Clean the voiceover | `/yt-edit` | `make_video.py clean` transcribes your recording, runs `deadair.py` (retakes, "um", silences over 1.2s; normal story pauses are kept), and writes `voice_clean.wav` plus the list of cuts. |
| Render | `pipeline/render.py` | Long video, captions, SOURCE cards, thumbnail. |
| Chapters | `/yt-chapters` | `make_video.py chapters` runs `chapters.py` on the final voiceover so the chapters match real timings and pass YouTube's rules. |
| Title + thumbnail | `/yt-package` | `title.py` lints the title and thumbnail text as a pair. |
| Description | `/yt-seo` | First two lines aimed at the search query, Sources section, chapters. |
| Shorts | `/yt-shorts` | Picks the 20-55s spans that stand on their own and writes a new first line; `make_video.py short` renders them 9:16. |
| Comments | `/yt-comment` | Wed and Sat comment sessions. |
| After 7 days | `/yt-retention` | Reads the YouTube Studio retention export and says which second people left. Fixes go into the next script. |
| Monthly | `/yt-audit` | Whole-channel check, ending in one fix. |
