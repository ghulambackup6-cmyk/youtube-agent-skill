"""Build the weekly production calendar as an .ics file for Google Calendar.

    python3 channel/calendar/make_calendar.py            # starts next Monday
    python3 channel/calendar/make_calendar.py 2026-11-30 # starts on a given Monday

Every block repeats weekly. Times are Asia/Karachi. Import the .ics in Google Calendar:
Settings > Import & export > Import, and pick a new calendar called "Channel" so you can
delete or recolour it in one go.
"""
import datetime as dt
import sys
import uuid
from pathlib import Path

# (weekday 0=Mon, start "HH:MM", minutes, title, description)
BLOCKS = [
    # --- Monday: Unseen Explained
    (0, "13:00", 15, "Post Short", "Approve and post today's Short on YouTube, Reels, Facebook and TikTok."),
    (0, "15:00", 180, "Research + script: Unseen Explained", "Source sheet first (quran.com, sunnah.com). Then /yt-script. Follow channel/script-format.md."),
    (0, "18:00", 60, "Record voiceover: Unseen Explained", "Record your voice for the script finished today."),
    (0, "19:00", 15, "PUBLISH: Unseen Explained (last week's)", "Long video goes live 7 PM PKT."),
    # --- Tuesday: visuals + History script
    (1, "13:00", 15, "Post Short", "Approve and post today's Short."),
    (1, "15:00", 120, "Visuals review: Unseen Explained", "Go through every scene. Approve, regenerate, or replace. Check no faces on Prophets/Sahaba."),
    (1, "17:00", 30, "Package: Unseen Explained", "/yt-package (title + thumbnail), /yt-seo, /yt-chapters."),
    (1, "17:30", 150, "Research + script: Forgotten Pages", "History: named sources only. /yt-script."),
    # --- Wednesday: History production
    (2, "13:00", 15, "Post Short", "Approve and post today's Short."),
    (2, "15:00", 60, "Record voiceover: Forgotten Pages", ""),
    (2, "16:00", 120, "Visuals review: Forgotten Pages", "Approve, regenerate, or replace each scene."),
    (2, "18:00", 30, "Package: Forgotten Pages", "/yt-package, /yt-seo, /yt-chapters."),
    (2, "19:00", 15, "PUBLISH: Forgotten Pages (last week's)", "Long video goes live 7 PM PKT."),
    (2, "19:15", 30, "Reply to comments", "/yt-comment: triage, reply, pin one."),
    # --- Thursday: Night Tales script + voice
    (3, "13:00", 15, "Post Short", "Approve and post today's Short."),
    (3, "15:00", 180, "Research + script: Night Tales", "Label Story or Narration. Every story ends with its real ayah/hadith."),
    (3, "18:00", 60, "Record voiceover: Night Tales", "Low, slow, late-night tone."),
    # --- Friday: Jumu'ah, lighter day
    (4, "13:00", 15, "Post Short", "Approve and post today's Short. Jumu'ah first."),
    (4, "16:00", 120, "Visuals review: Night Tales", "Approve, regenerate, or replace each scene."),
    (4, "18:00", 30, "Package: Night Tales", "/yt-package, /yt-seo, /yt-chapters."),
    # --- Saturday: Shorts + Night Tales release
    (5, "13:00", 15, "Post Short", "Approve and post today's Short."),
    (5, "15:00", 150, "Cut 7 Shorts for next week", "/yt-shorts on this week's 3 videos. New first line for each."),
    (5, "17:30", 60, "Approval queue", "Final check of next week's 3 long videos + 7 Shorts, then schedule them."),
    (5, "21:00", 15, "PUBLISH: Night Tales (last week's)", "Long video goes live 9 PM PKT (horror does better late)."),
    (5, "21:15", 30, "Reply to comments", "/yt-comment."),
    # --- Sunday: review + plan
    (6, "13:00", 15, "Post Short", "Approve and post today's Short."),
    (6, "15:00", 90, "Weekly review + plan", "/yt-retention on last week's videos, /yt-viral for ideas, /yt-plan for next week's 3 topics."),
    (6, "16:30", 120, "Buffer / catch-up", "Anything that slipped. If nothing did, research ahead."),
]

DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def next_monday(today):
    return today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)


def esc(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build(start):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//youtube-agent-skill//channel calendar//EN",
        "CALSCALE:GREGORIAN", "X-WR-CALNAME:Channel", "X-WR-TIMEZONE:Asia/Karachi",
        "BEGIN:VTIMEZONE", "TZID:Asia/Karachi", "BEGIN:STANDARD", "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0500", "TZOFFSETTO:+0500", "TZNAME:PKT", "END:STANDARD", "END:VTIMEZONE",
    ]
    for wd, hhmm, mins, title, desc in BLOCKS:
        h, m = map(int, hhmm.split(":"))
        s = dt.datetime.combine(start + dt.timedelta(days=wd), dt.time(h, m))
        e = s + dt.timedelta(minutes=mins)
        out += [
            "BEGIN:VEVENT", f"UID:{uuid.uuid5(uuid.NAMESPACE_URL, title + hhmm + str(wd))}@channel",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Asia/Karachi:{s:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Asia/Karachi:{e:%Y%m%dT%H%M%S}",
            f"RRULE:FREQ=WEEKLY;BYDAY={DAYS[wd]}",
            f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(desc)}",
            "BEGIN:VALARM", "TRIGGER:-PT10M", "ACTION:DISPLAY", f"DESCRIPTION:{esc(title)}", "END:VALARM",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


if __name__ == "__main__":
    start = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else next_monday(dt.date.today())
    if start.weekday() != 0:
        sys.exit("start date must be a Monday")
    path = Path(__file__).with_name("channel-week.ics")
    path.write_text(build(start))
    total = sum(b[2] for b in BLOCKS)
    print(f"wrote {path} starting {start}: {len(BLOCKS)} weekly blocks, {total/60:.1f} hours a week")
