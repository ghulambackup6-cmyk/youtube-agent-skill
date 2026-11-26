# One-time setup of the Fajrlight Stories video pipeline on Windows.
# Right-click the Start button > Terminal (or PowerShell), then paste:
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1
# It installs Git, Python and ffmpeg (free, via winget), downloads the pipeline into
# Documents\youtube-agent-skill, and makes the first set of AI pictures for video 001.

$ErrorActionPreference = "Stop"
$args_ = "--accept-package-agreements", "--accept-source-agreements", "-e", "--silent"

foreach ($id in "Git.Git", "Python.Python.3.12", "Gyan.FFmpeg") {
    Write-Host "Installing $id (skipped if already installed)..."
    winget install --id $id @args_ 2>$null | Out-Null
}

# pick up the new programs without reopening the window
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path", "User")

$repo = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "youtube-agent-skill"
if (Test-Path $repo) {
    git -C $repo pull
} else {
    git clone -b claude/project-thread-ixgssz https://github.com/ghulambackup6-cmyk/youtube-agent-skill.git $repo
}
Set-Location $repo

python -m pip install --upgrade pip
python -m pip install -r pipeline/requirements.txt
python -m pip install faster-whisper "av<14"   # optional: exact timing from your voice
# The channel voice (free clone, Chatterbox, MIT licence) in its own environment so its
# torch version cannot clash with anything else. About 4 GB download the first time.
python -m venv tts-venv
tts-venv\Scripts\python -m pip install chatterbox-tts faster-whisper "setuptools<81"
Add-Content .env "CHATTERBOX_PYTHON=$PWD\tts-venv\Scripts\python.exe"

python pipeline/make_video.py new channel/scripts/001-three-questions-of-the-grave.md
python pipeline/make_video.py images videos/001-three-questions-of-the-grave --generate
python pipeline/make_video.py render videos/001-three-questions-of-the-grave --test-voice

Write-Host ""
Write-Host "Done. Opening the review page. Leave this window open while you review."
Start-Process "http://localhost:8765/review.html"
python pipeline/review.py serve videos/001-three-questions-of-the-grave
