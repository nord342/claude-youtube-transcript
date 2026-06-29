#!/usr/bin/env python3
"""
yt_transcript.py — Reliably fetch a YouTube video's transcript locally.

Strategy: call yt-dlp once with --dump-single-json (using browser cookies to
beat YouTube's bot checks), read the subtitle/auto-caption URLs out of the
returned metadata, fetch the chosen track over HTTP, and parse it into clean
text. No video is downloaded and no API key is required.

Examples:
    python3 yt_transcript.py "https://youtu.be/dQw4w9WgXcQ"
    python3 yt_transcript.py --timestamps "https://www.youtube.com/watch?v=..."
    python3 yt_transcript.py --lang es "https://youtu.be/..."
    python3 yt_transcript.py --list-langs "https://youtu.be/..."
    python3 yt_transcript.py --browser safari "https://youtu.be/..."
    python3 yt_transcript.py --json "https://youtu.be/..."
"""

import argparse
import json
import re
import ssl
import subprocess
import sys
import urllib.request

# Browsers tried (in order) when --browser is "auto". Chrome first because it
# is the most reliable for passing YouTube's bot check on macOS.
BROWSER_FALLBACKS = ["chrome", "safari", "brave", "edge", "firefox"]


def eprint(*args):
    print(*args, file=sys.stderr)


def extract_video_id(url_or_id: str):
    """Accept a full URL (watch, youtu.be, shorts, embed, with timestamps) or a
    bare 11-char video id and return the canonical id, or None."""
    s = url_or_id.strip()
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", s):
        return s
    patterns = [
        r"(?:v=|/shorts/|/embed/|/v/|youtu\.be/)([0-9A-Za-z_-]{11})",
        r"[?&]v=([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            return m.group(1)
    return None


def run_ytdlp_json(url: str, browser: str):
    """Run yt-dlp --dump-single-json. If browser is 'auto', try each browser's
    cookies in turn, then a final attempt with no cookies. Returns parsed dict."""
    browsers = [browser] if browser != "auto" else list(BROWSER_FALLBACKS)
    attempts = [("--cookies-from-browser", b) for b in browsers]
    attempts.append((None, None))  # last resort: no cookies

    last_err = ""
    for flag, value in attempts:
        cmd = ["yt-dlp", "--skip-download", "--dump-single-json",
               "--no-warnings", "--no-playlist"]
        if flag:
            cmd += [flag, value]
        cmd.append(url)
        label = f"cookies from {value}" if value else "no cookies"
        eprint(f"[yt-transcript] trying yt-dlp ({label})...")
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            sys.exit("ERROR: yt-dlp is not installed. Install it with: "
                     "brew install yt-dlp   (or)   pipx install yt-dlp")
        except subprocess.TimeoutExpired:
            last_err = "yt-dlp timed out"
            continue
        if out.returncode == 0 and out.stdout.strip():
            try:
                return json.loads(out.stdout)
            except json.JSONDecodeError:
                last_err = "could not parse yt-dlp JSON output"
                continue
        last_err = (out.stderr or out.stdout or "unknown error").strip()
        # A locked cookie DB or missing browser → just try the next option.
    sys.exit("ERROR: yt-dlp could not fetch video metadata.\n"
             f"Last error:\n{last_err}\n\n"
             "Tips: make sure the video is public/unlisted, your browser is "
             "installed and signed in to YouTube, and yt-dlp is up to date "
             "(yt-dlp -U).")


def pick_track(info: dict, lang: str):
    """Choose a subtitle track. Prefer human (manual) subtitles over
    auto-captions, prefer the requested language, prefer the json3 format.
    Returns (url, ext, chosen_lang, is_auto) or (None, ...)."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    def lang_candidates(track_map):
        keys = list(track_map.keys())
        ordered = []
        # exact match first, then prefix match (e.g. "en" matches "en-US"),
        # then any English, then anything.
        ordered += [k for k in keys if k == lang]
        ordered += [k for k in keys if k.split("-")[0] == lang and k != lang]
        if lang != "en":
            ordered += [k for k in keys if k.split("-")[0] == "en"]
        ordered += [k for k in keys if k not in ordered]
        return ordered

    for is_auto, track_map in ((False, manual), (True, auto)):
        for k in lang_candidates(track_map):
            fmts = track_map.get(k) or []
            # Prefer structured json3, then vtt, then anything.
            for want in ("json3", "vtt", "srv3", "srv1", "ttml"):
                for f in fmts:
                    if f.get("ext") == want and f.get("url"):
                        return f["url"], want, k, is_auto
            for f in fmts:
                if f.get("url"):
                    return f["url"], f.get("ext", "?"), k, is_auto
    return None, None, None, None


def _ssl_context():
    """Build a verifying SSL context. Prefer certifi's CA bundle (handles the
    common 'no local issuer certificate' error with python.org Python on
    macOS); fall back to the system default."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        # Last resort for misconfigured local CA stores: retry without
        # verification. Captions are public, non-sensitive data served from a
        # short-lived signed Google URL, so this is an acceptable fallback.
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            eprint("[yt-transcript] warning: TLS cert verification failed; "
                   "retrying without verification. To fix permanently run: "
                   "pip3 install certifi  (or the 'Install Certificates' "
                   "command in your Python folder).")
            unverified = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=60, context=unverified) as resp:
                return resp.read().decode("utf-8", errors="replace")
        raise


def fmt_ts(ms: float) -> str:
    s = int(ms // 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def parse_json3(raw: str, timestamps: bool):
    data = json.loads(raw)
    lines = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if not text:
            continue
        if timestamps:
            lines.append(f"[{fmt_ts(ev.get('tStartMs', 0))}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines) if timestamps else " ".join(lines)


def parse_vtt(raw: str, timestamps: bool):
    """Parse WebVTT, dropping cue timing/markup and de-duplicating the rolling
    repeated lines that YouTube auto-captions produce."""
    out = []
    seen_recent = []
    cur_ts = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        m = re.match(r"(\d{2}:\d{2}:\d{2})\.\d{3}\s*-->", line)
        if m:
            cur_ts = m.group(1).lstrip("0:") or "0"
            cur_ts = m.group(1)
            continue
        if "-->" in line:
            continue
        text = re.sub(r"<[^>]+>", "", line)            # inline tags
        text = re.sub(r"\{[^}]+\}", "", text).strip()  # cue settings
        if not text or text in seen_recent:
            continue
        seen_recent = (seen_recent + [text])[-4:]
        if timestamps and cur_ts:
            out.append(f"[{cur_ts}] {text}")
        else:
            out.append(text)
    return "\n".join(out) if timestamps else " ".join(out)


def main():
    ap = argparse.ArgumentParser(description="Fetch a YouTube transcript locally via yt-dlp.")
    ap.add_argument("url", help="YouTube URL or 11-char video id")
    ap.add_argument("--lang", default="en", help="preferred language code (default: en)")
    ap.add_argument("--browser", default="auto",
                    help="cookie source browser: auto|chrome|safari|brave|edge|firefox (default: auto)")
    ap.add_argument("--timestamps", action="store_true", help="include [mm:ss] timestamps")
    ap.add_argument("--list-langs", action="store_true", help="list available caption languages and exit")
    ap.add_argument("--json", action="store_true", help="emit JSON: metadata + transcript")
    args = ap.parse_args()

    vid = extract_video_id(args.url)
    if not vid:
        sys.exit(f"ERROR: could not find a YouTube video id in: {args.url}")
    url = f"https://www.youtube.com/watch?v={vid}"

    info = run_ytdlp_json(url, args.browser)
    title = info.get("title", "")
    uploader = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration")

    if args.list_langs:
        manual = sorted((info.get("subtitles") or {}).keys())
        auto = sorted((info.get("automatic_captions") or {}).keys())
        eprint(f"Title: {title}")
        print("Manual subtitles:", ", ".join(manual) if manual else "(none)")
        print("Auto-captions:", ", ".join(auto[:40]) + (" ..." if len(auto) > 40 else "")
              if auto else "(none)")
        return

    sub_url, ext, chosen_lang, is_auto = pick_track(info, args.lang)
    if not sub_url:
        sys.exit("ERROR: no captions/subtitles available for this video.")

    raw = http_get(sub_url)
    if ext == "json3":
        transcript = parse_json3(raw, args.timestamps)
    elif ext in ("vtt", "srv3", "srv1", "ttml"):
        transcript = parse_vtt(raw, args.timestamps)
    else:
        transcript = parse_vtt(raw, args.timestamps)

    if not transcript.strip():
        sys.exit("ERROR: caption track was empty after parsing.")

    src = "auto-generated" if is_auto else "manual"
    if args.json:
        print(json.dumps({
            "video_id": vid,
            "url": url,
            "title": title,
            "uploader": uploader,
            "duration_seconds": duration,
            "language": chosen_lang,
            "caption_source": src,
            "transcript": transcript,
        }, ensure_ascii=False, indent=2))
    else:
        dur = fmt_ts(duration * 1000) if duration else "?"
        eprint(f"[yt-transcript] {title} — {uploader} ({dur}) "
               f"| lang={chosen_lang} | {src}")
        print(transcript)


if __name__ == "__main__":
    main()
