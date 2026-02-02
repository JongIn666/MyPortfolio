#!/usr/bin/env python3
"""
download_html_css.py

Usage:
  python download_html_css.py "https://example.com" --out site_dump

Outputs:
  site_dump/index.html
  site_dump/assets/css/*.css
"""

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup


def safe_filename(name: str, default: str = "file") -> str:
    """Make a string safe for filesystem use."""
    name = name.strip()
    name = re.sub(r"[^\w\-.]+", "_", name)
    return name or default


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def fetch(url: str, session: requests.Session, timeout: int = 20) -> requests.Response:
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp


def guess_css_name(css_url: str, idx: int) -> str:
    parsed = urlparse(css_url)
    base = os.path.basename(parsed.path)
    if base and base.lower().endswith(".css"):
        return safe_filename(base)
    if base:
        return safe_filename(base) + ".css"
    return f"style_{idx}.css"


def main():
    # parser = argparse.ArgumentParser(description="Download HTML + linked CSS from a webpage.")
    # parser.add_argument("url", help="Target page URL (e.g., https://example.com)")
    # parser.add_argument("--out", default="site_dump", help="Output folder")
    # parser.add_argument("--timeout", type=int, default=20, help="Request timeout (seconds)")
    # args = parser.parse_args()

    target_url = "https://www.canva.com/design/DAHACvYL71I/293rQA29YER5rxNPb1QX-A/view#1"
    out_dir = Path.cwd() / "example"
    css_dir = out_dir / "assets" / "css"

    ensure_dir(out_dir)
    ensure_dir(css_dir)

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        page_resp = fetch(target_url, session, timeout=args.timeout)
    except requests.RequestException as e:
        print(f"[error] Failed to fetch page: {e}", file=sys.stderr)
        sys.exit(1)

    # Use apparent encoding if needed
    page_resp.encoding = page_resp.apparent_encoding
    html = page_resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Find external stylesheets
    link_tags = soup.find_all("link", rel=lambda v: v and "stylesheet" in str(v).lower())

    downloaded = {}  # css_url -> local_rel_path

    for i, link in enumerate(link_tags, start=1):
        href = link.get("href")
        if not href:
            continue

        # Turn relative href into absolute URL and drop fragments (#...)
        abs_url = urljoin(page_resp.url, href)
        abs_url, _frag = urldefrag(abs_url)

        # Skip non-http(s)
        scheme = urlparse(abs_url).scheme.lower()
        if scheme not in ("http", "https"):
            continue

        # Download
        try:
            css_resp = fetch(abs_url, session, timeout=args.timeout)
        except requests.RequestException as e:
            print(f"[warn] Failed to fetch CSS: {abs_url} ({e})", file=sys.stderr)
            continue

        css_resp.encoding = css_resp.apparent_encoding
        css_text = css_resp.text

        css_name = guess_css_name(abs_url, i)
        local_path = css_dir / css_name
        local_path.write_text(css_text, encoding="utf-8")

        local_rel = os.path.relpath(local_path, out_dir).replace("\\", "/")
        downloaded[abs_url] = local_rel

        # Rewrite the link href to local file path
        link["href"] = local_rel

        print(f"[ok] CSS saved: {abs_url} -> {local_rel}")

    # Save rewritten HTML
    index_path = out_dir / "index.html"
    index_path.write_text(str(soup), encoding="utf-8")
    print(f"[ok] HTML saved: {index_path}")

    # Summary
    print("\nDone.")
    print(f"Output directory: {out_dir.resolve()}")
    print(f"CSS files downloaded: {len(downloaded)}")


if __name__ == "__main__":
    main()
