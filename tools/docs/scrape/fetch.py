from __future__ import annotations

from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ATTEMPTS = 3
TIMEOUT = 30


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "agent-db docs scraper"})
    attempt = 0
    while True:
        action = "Fetching" if attempt == 0 else f"Retrying ({attempt + 1}/{ATTEMPTS})"
        print(f"{action} {url}", flush=True)
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                status = response.status
                if status != 200:
                    raise RuntimeError(f"GET {url} returned HTTP {status}")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            if attempt == ATTEMPTS - 1:
                raise
        except TimeoutError, URLError:
            if attempt == ATTEMPTS - 1:
                raise
        sleep(2**attempt)
        attempt += 1
