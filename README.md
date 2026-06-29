# YouTube Transcript for Claude Code

Paste a YouTube link into Claude Code and get the full transcript — instantly, **locally**, with **no API key**.

This is a [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) skill. Once installed, you just drop a YouTube URL into the chat ("summarize this video: …", or just the link) and Claude fetches the transcript automatically, then summarizes / quotes / answers questions about it.

## Why this one?

Most YouTube-transcript tools and hosted MCP connectors get throttled or blocked by YouTube's bot detection and fail constantly. This skill runs [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) **locally using your browser cookies**, which is the reliable way to fetch captions from your own machine. The result:

- ✅ **Reliable** — uses your signed-in browser session, so it gets past the "confirm you're not a bot" wall.
- ✅ **No API key, no account, nothing to host.**
- ✅ **Fast** — only the caption track is fetched, never the video.
- ✅ Handles `youtube.com/watch`, `youtu.be`, `/shorts`, `/embed`, bare video IDs, and URLs with timestamps.
- ✅ Prefers human-made subtitles over auto-captions; supports any language; optional `[mm:ss]` timestamps.

## Requirements

- macOS / Linux / WSL
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- `yt-dlp` — install with `brew install yt-dlp` (or `pipx install yt-dlp`)
- Python 3.8+ (pre-installed on macOS; `certifi` recommended: `pip3 install certifi`)
- A browser signed in to YouTube (Chrome recommended)

## Install

In Claude Code:

```
/plugin marketplace add nord342/claude-youtube-transcript
/plugin install youtube-transcript
```

Then restart Claude Code (or reload plugins) if prompted.

## Usage

Just talk to Claude naturally:

```
Summarize this video: https://youtu.be/dQw4w9WgXcQ
```
```
https://www.youtube.com/watch?v=... what are the 3 main takeaways?
```
```
Get me the transcript of this short with timestamps: https://youtube.com/shorts/...
```

Claude will run the skill, tell you which video it found, and answer.

### Running the script directly (optional)

The skill is just a wrapper around a standalone script you can also run yourself:

```bash
python3 yt_transcript.py "https://youtu.be/dQw4w9WgXcQ"
python3 yt_transcript.py --timestamps "https://youtu.be/..."
python3 yt_transcript.py --lang es "https://youtu.be/..."
python3 yt_transcript.py --list-langs "https://youtu.be/..."
python3 yt_transcript.py --browser safari "https://youtu.be/..."
python3 yt_transcript.py --json "https://youtu.be/..."   # transcript + metadata
```

The script lives at
`plugins/youtube-transcript/skills/youtube-transcript/scripts/yt_transcript.py`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `yt-dlp is not installed` | `brew install yt-dlp` or `pipx install yt-dlp` |
| "Sign in to confirm you're not a bot" / metadata fails | Sign in to YouTube in Chrome, then retry. Try `--browser chrome`. Update yt-dlp: `yt-dlp -U`. |
| `no captions/subtitles available` | The video genuinely has no captions. |
| TLS / certificate error | The script auto-falls back, but the clean fix is `pip3 install certifi`. |
| Wrong language | Use `--list-langs` to see options, then `--lang <code>`. |

## How it works

1. `yt-dlp --dump-single-json` (with `--cookies-from-browser`) returns the video metadata, including signed URLs for every available caption track.
2. The script picks the best track (manual > auto, your language, `json3` format) and fetches just that caption file over HTTPS.
3. It parses `json3`/WebVTT into clean text (de-duplicating the rolling lines auto-captions produce), optionally with timestamps.

No video data is downloaded. Cookies are read by `yt-dlp` directly from your local browser and are never stored or transmitted anywhere except to YouTube.

## License

MIT © nord342
