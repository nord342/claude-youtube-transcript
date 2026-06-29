---
name: youtube-transcript
description: Fetch the transcript/captions of any YouTube video. Use whenever the user pastes a YouTube link (youtube.com, youtu.be, shorts) or asks for a video's transcript, subtitles, captions, or "what does this video say / summarize this video". Runs locally via yt-dlp with browser cookies, so it works reliably without an API key.
---

# YouTube Transcript

Get the full transcript of a YouTube video so you can summarize it, quote it,
answer questions about it, or pull out key points — all locally, no API key.

## When to use

Trigger this skill whenever the user:
- Pastes any YouTube URL (`youtube.com/watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`), with or without a question.
- Asks for a video's transcript, captions, or subtitles.
- Asks you to summarize, analyze, quote, or answer questions about a YouTube video.

## How to fetch a transcript

Run the bundled script. It calls `yt-dlp` with your browser cookies (which is
what reliably gets past YouTube's bot checks), reads the caption track, and
prints clean text to stdout. Progress/metadata go to stderr.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/youtube-transcript/scripts/yt_transcript.py" "<YOUTUBE_URL>"
```

If `${CLAUDE_PLUGIN_ROOT}` is not set in your environment, use the script's
path inside this skill directory (`scripts/yt_transcript.py`).

### Options

- `--timestamps` — prefix each line with `[mm:ss]` (use when the user wants to cite or jump to moments).
- `--lang <code>` — preferred caption language, e.g. `--lang es` (default `en`; falls back to English, then any available).
- `--list-langs` — list which caption languages exist for the video, then exit. Use this if the default language isn't what the user wanted.
- `--browser <name>` — cookie source: `auto` (default), `chrome`, `safari`, `brave`, `edge`, `firefox`. `auto` tries each, then no cookies.
- `--json` — emit `{title, uploader, duration_seconds, language, caption_source, transcript}` as JSON. Use when you want the metadata too.

### Typical flow

1. Run the script with the user's URL. For long videos, prefer `--json` or plain text and then work from the captured output.
2. Lead your answer with the video **title** and **channel** (shown on stderr, or in `--json`), so the user knows it fetched the right video.
3. Then do what the user asked — summarize, extract steps/quotes, answer a question, etc. If they didn't ask for anything specific, give a concise summary and offer the full transcript.
4. Don't paste a huge raw transcript back unless the user explicitly asks for the full text.

## Troubleshooting

- **"yt-dlp is not installed"** → `brew install yt-dlp` (or `pipx install yt-dlp`).
- **Metadata fetch fails / "Sign in to confirm you're not a bot"** → the user must be signed in to YouTube in the chosen browser. Try `--browser chrome` explicitly, or `yt-dlp -U` to update. A logged-in Chrome profile is the most reliable on macOS.
- **"no captions/subtitles available"** → the video genuinely has no captions (some do not). There is no transcript to fetch; tell the user.
- **TLS / certificate errors** → the script auto-falls back, but the clean fix is `pip3 install certifi`.

## Notes

- No video is downloaded — only the caption track. It's fast.
- Prefers human-made (manual) subtitles over auto-generated captions when both exist.
- Works on unlisted videos you can access; will not work on private/members-only videos your browser can't see.
