from __future__ import annotations

from urllib.request import Request, urlopen


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "agent-db docs scraper"})
    with urlopen(request, timeout=30) as response:
        status = response.status
        if status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {status}")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")
