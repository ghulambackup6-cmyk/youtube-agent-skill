# Script format and research rules

Every long video script follows this file. It extends `/yt-script` (hooks, beats, ON SCREEN
marks) with the research and sourcing rules this channel needs.

## Step 1. Research before writing

Make a **source sheet** first. Writing starts only when every claim in the outline has a row.

| # | Claim used in the video | Type | Exact reference | Grading / translation | Link | Checked |
|---|---|---|---|---|---|---|

### Approved sources

| Need | Use | Notes |
|---|---|---|
| Quran text and translation | quran.com | Always name the translation. Default: *The Clear Quran* (Dr. Mustafa Khattab), the one quran.com shows by default. Sahih International is fine too, but name it. |
| Hadith text and grading | sunnah.com | Cite as *Book number* (e.g. Sahih al-Bukhari 1338). Copy the grading shown on the page and who graded it (e.g. "Sahih (Al-Albani)", "Hasan (Darussalam)"). |
| Explaining an ayah | Tafsir Ibn Kathir (quran.com tafsir tab) | Say "Ibn Kathir explains...". |
| Rulings and differences | Named scholars or IslamQA / Yaqeen Institute articles | Never present a ruling as the channel's own. |
| History | Ibn Kathir *al-Bidaya wan-Nihaya*, al-Tabari *Tarikh*, Ibn Hisham *Sirah*, modern academic books | Name the book in the description. |

### Grading rules

- **Sahih al-Bukhari and Sahih Muslim:** accepted as authentic. Say "in Sahih al-Bukhari".
- **Other books (Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah, Ahmad):** use only hadith graded Sahih or
  Hasan on sunnah.com, and say the grading out loud or on screen.
- **Da'if (weak) or Mawdu' (fabricated):** never used as evidence. Can only appear in a "Myths"
  segment, clearly labelled as weak or fabricated.
- **Not found:** if a popular story has no source, the script says "this story is popular, but we
  could not find it in any authentic source".
- Never quote a hadith from memory. Open the page, copy the reference, record it in the sheet.

## Step 2. Hooks

Write 5 hooks from `skills/yt-script/hooks.json`, score them with:

```bash
python3 skills/yt-script/hookscore.py hooks.txt
```

Keep the top 2 and show both. For religious topics, the hook must not exaggerate the source:
the payoff has to be something the Quran or hadith actually says.

## Step 3. The script

```
TITLE (working):
SERIES: Unseen Explained | Night Tales | Forgotten Pages
LABEL: (Night Tales only) Story (fiction, inspired by Islamic teachings) | Narration (sourced)
TARGET LENGTH: x min (~150 words per minute)

[0:00 HOOK]
VO: ...
[ON SCREEN: ...]

[0:15 THE TURN] what this video will do, in one sentence. No intro.

[SERIES STING 3s]

[BEAT 1 ...]
VO: ...
[ON SCREEN: ...]
[SOURCE CARD: Sahih al-Bukhari 1338]   <- every quote gets a card

...

[PAYOFF] deliver what the hook promised, explicitly.

[LESSON] one sentence the viewer takes away.

[CLOSE] one ask only.
```

Rules:
- Every beat has `[ON SCREEN: ...]`. That line becomes the image prompt in the video pipeline.
- Every Quran or hadith quote has a `[SOURCE CARD: ...]` with the exact reference.
- Prophets and Sahaba: describe them on screen as "figure with face covered by soft white light".
  They never speak in first person; the narrator quotes them.
- Write ﷺ after the Prophet's name in the script; say "sallallahu alayhi wa sallam" or "peace be
  upon him" in the voiceover.

## Step 4. Package and SEO

- Titles: write 10, run `python3 skills/yt-package/title.py titles.txt`, keep the top 3.
- Thumbnail: 3 words max, different from the title, series colour.
- Description: `/yt-seo`. The first two lines answer the search query. Then a **Sources** section
  listing every reference from the source sheet with links. This builds trust and helps search.
- Chapters: `/yt-chapters` from the final voiceover transcript.

## Step 5. Checks before approval

- [ ] Every claim has a row in the source sheet, with a link.
- [ ] No weak hadith used as evidence.
- [ ] Translation named for every ayah.
- [ ] Night Tales: Story or Narration label said in the first 30 seconds and in the description.
- [ ] No face visible on any Prophet or Sahabi in any frame or thumbnail.
- [ ] YouTube "altered or synthetic content" box ticked if any scene looks realistic.
- [ ] Ahmed has recorded the voiceover and approved the visuals.
