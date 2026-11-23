# Channel foundation

Everything the channel runs on. The skills in `skills/` read these files.

| File | What it is |
|---|---|
| [channel-names.md](channel-names.md) | 8 name ideas. Pick one before creating the Gmail. |
| [series.md](series.md) | The 3 series: Unseen Explained, Night Tales, Forgotten Pages. |
| [voice.md](voice.md) | The voice file every skill reads. Copy to `~/.claude/youtube/voice.md`. |
| [script-format.md](script-format.md) | How every script is researched, sourced and written. |
| [scripts/001-three-questions-of-the-grave.md](scripts/001-three-questions-of-the-grave.md) | First full sample script, with a verified source sheet. |
| [calendar/channel-week.ics](calendar/channel-week.ics) | The weekly calendar, ready to import into Google Calendar. |

## Publishing schedule (Pakistan time)

| Day | Long video | Short |
|---|---|---|
| Mon | **Unseen Explained**, 7 PM | 1 PM |
| Tue | | 1 PM |
| Wed | **Forgotten Pages**, 7 PM | 1 PM |
| Thu | | 1 PM |
| Fri | (Jumu'ah, no long video) | 1 PM |
| Sat | **Night Tales**, 9 PM | 1 PM |
| Sun | | 1 PM |

3 long videos and 7 Shorts a week. Each video is made one week before it goes out, so there is
always a finished week in the queue. First 2 weeks: make 2 long videos (skip Forgotten Pages) while
you learn the workflow. Change the times once YouTube Analytics shows when your viewers are online.

## Weekly work blocks (about 30 hours)

| Day | Work |
|---|---|
| Mon | Research + script Unseen Explained (3h), record voiceover (1h) |
| Tue | Visuals review (2h), packaging (30m), research + script Forgotten Pages (2.5h) |
| Wed | Record voiceover (1h), visuals review (2h), packaging (30m), comments (30m) |
| Thu | Research + script Night Tales (3h), record voiceover (1h) |
| Fri | Visuals review (2h), packaging (30m). Lighter day for Jumu'ah. |
| Sat | Cut 7 Shorts (2.5h), approval queue and scheduling (1h), comments (30m) |
| Sun | Weekly review and plan (1.5h), buffer (2h) |

Plus 15 minutes a day to approve and post the Short. That leaves 5 to 10 hours of your 35 to 40
for building the video pipeline in the first weeks.

## Google Calendar

Import `calendar/channel-week.ics`: Google Calendar on a computer > Settings > Import & export >
Import. Choose a new calendar called "Channel" first so you can recolour or delete all of it at
once. Every block repeats weekly with a 10-minute reminder.

To change times, edit `BLOCKS` in `calendar/make_calendar.py` and run:

```bash
python3 channel/calendar/make_calendar.py 2026-11-30   # any Monday
```
