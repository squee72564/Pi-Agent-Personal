"""Bounded Tavily CLI output for Pi. Standard library only; no MCP or API keys."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

CACHE = Path(tempfile.gettempdir()) / "pi-tavily-web"
CACHE_TTL = 3600


def fail(message):
    # Avoid exposing common credential shapes in CLI diagnostics.
    message = re.sub(r"tvly-[\w-]+|eyJ[\w.-]+", "[REDACTED]", str(message))
    print("Error: " + message[:1500], file=sys.stderr)
    raise SystemExit(1)


def invoke(args, as_json=True):
    cli = shutil.which("tvly.cmd") or shutil.which("tvly")
    if not cli:
        fail("tvly is not on PATH. Ask the user to install it or reopen the terminal.")
    command = [cli] + (["--json"] if as_json else []) + args
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        fail("Tavily CLI timed out after 120 seconds.")
    except OSError:
        fail("Could not start Tavily CLI. Check installation and PATH.")
    if not as_json:
        return result
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail("Tavily returned non-JSON output. Raw output withheld; check tvly auth locally.")
    if not isinstance(data, dict):
        fail("Unexpected Tavily JSON response shape.")
    if result.returncode or data.get("error"):
        fail(data.get("error") or "Tavily failed; check authentication, quota, and service status.")
    if str(data.get("auth_mode", "")).lower() in {"anonymous", "unauthenticated"}:
        fail("Tavily used anonymous mode. Ask the user to run tvly login, then retry.")
    return data


def authenticate():
    result = invoke(["auth"], as_json=False)
    # Never print auth stdout/stderr: this CLI displays part of its credential.
    output = result.stdout + result.stderr
    if result.returncode == 0 and re.search(r"\bauthenticated via\b", output, re.I):
        print("Tavily CLI is authenticated. Credential details withheld.")
        return
    fail("Authentication missing or unrecognized. Ask the user to run tvly login in their terminal and finish browser authentication.")


def public_url(value):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"https", "http"} or not host or parsed.username or parsed.password:
            raise ValueError()
        if host in {"localhost", "metadata.google.internal"} or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
    except ValueError:
        raise argparse.ArgumentTypeError("Use a public HTTP(S) URL without embedded credentials.")
    # This is a basic input check, not DNS/redirect isolation. Tavily fetches remotely.
    return value


def compact(value):
    """Collapse layout whitespace without summarizing or rewriting source words."""
    return " ".join(str(value or "").split())


def search(args):
    data = invoke(["search", args.query, "--max-results", str(args.max_results)])
    results = data.get("results", [])
    if not isinstance(results, list):
        fail("Unexpected search results shape.")
    print("Search:", compact(args.query))
    print("Searched at:", datetime.now().astimezone().isoformat(timespec="seconds"),
          "| Source dates may differ.")
    for index, item in enumerate(results[:args.max_results], 1):
        print(f"\n{index}. {compact(item.get('title') or '(untitled)')[:300]}")
        print(compact(item.get("url"))[:2000])
        if item.get("published_date"):
            print("Published:", compact(item["published_date"])[:100])
        if args.snippet_chars:
            content = compact(item.get("content"))
            suffix = " [truncated]" if len(content) > args.snippet_chars else ""
            print(content[:args.snippet_chars] + suffix)
    if not results:
        print("No search results returned.")


def extract(args):
    key = hashlib.sha256(args.url.encode()).hexdigest()
    path = CACHE / (key + ".json")
    page = None
    if not args.refresh:
        try:
            if time.time() - path.stat().st_mtime < CACHE_TTL:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                if candidate.get("url") == args.url and isinstance(candidate.get("text"), str):
                    page = candidate
        except (OSError, ValueError, AttributeError):
            pass
    cached = page is not None
    if page is None:
        data = invoke(["extract", args.url])
        results = data.get("results") or []
        if not results:
            failed = data.get("failed_results") or []
            reason = failed[0].get("error") if failed and isinstance(failed[0], dict) else None
            fail(reason or "No page extracted; it may be blocked, unavailable, or require login.")
        item = results[0]
        text = item.get("raw_content") or item.get("content")
        if not isinstance(text, str) or not text.strip():
            fail("Extraction returned no readable content.")
        page = {"url": args.url, "source_url": item.get("url") or args.url,
                "title": item.get("title") or "(untitled)", "text": text,
                "fetched_at": datetime.now(timezone.utc).isoformat()}
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            # Atomic replacement prevents partially written cache entries.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CACHE,
                                             delete=False, suffix=".tmp") as temporary:
                json.dump(page, temporary, ensure_ascii=False)
                temporary_path = temporary.name
            os.replace(temporary_path, path)
        except OSError:
            print("Warning: could not cache this extraction.", file=sys.stderr)
    text = page["text"]
    end = min(len(text), args.start + args.max_chars)
    print("Title:", str(page["title"])[:300])
    print("Source:", str(page["source_url"])[:2000])
    print("Fetched:", page["fetched_at"], "| Cache:", "hit" if cached else "miss")
    print(f"Extracted characters: {len(text)} | Showing [{args.start}:{end}]\n")
    print(text[args.start:end])
    if end < len(text):
        print(f"\n[Truncated. Continue with --start {end} --max-chars {args.max_chars} for this URL.]")
    else:
        print("\n[End of extracted text; this does not guarantee complete webpage coverage.]")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("auth").set_defaults(run=lambda _: authenticate())
    find = commands.add_parser("search")
    find.add_argument("query")
    find.add_argument("--max-results", type=int, choices=range(1, 7), default=3,
                      help="Results: 1-6 (default: 3)")
    find.add_argument("--snippet-chars", type=int, default=450,
                      help="Characters per whitespace-compacted snippet: 0-4000 (default: 450); 0 shows titles/URLs only")
    find.set_defaults(run=search)
    read = commands.add_parser("extract")
    read.add_argument("url", type=public_url)
    read.add_argument("--start", type=int, default=0)
    read.add_argument("--max-chars", type=int, default=12000,
                      help="Characters per response: 1-25000 (default: 12000); use --start to continue")
    read.add_argument("--refresh", action="store_true")
    read.set_defaults(run=extract)
    args = parser.parse_args()
    if args.command == "search" and not 0 <= args.snippet_chars <= 4000:
        parser.error("--snippet-chars must be between 0 and 4000")
    if args.command == "extract" and (args.start < 0 or not 1 <= args.max_chars <= 25000):
        parser.error("--start must be nonnegative; --max-chars must be between 1 and 25000")
    args.run(args)


if __name__ == "__main__":
    main()
