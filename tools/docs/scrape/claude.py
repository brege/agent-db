from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .fetch import fetch_text

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "https://code.claude.com"
DOCS_PREFIX = "/docs/en/"
OUTPUT_ROOT = ROOT / "docs" / "reference" / "claude"
DISCOVERY_SEED = "https://code.claude.com/docs/en/glossary"


@dataclass(frozen=True)
class Page:
    url: str
    href: str
    output: Path

    @classmethod
    def from_href(cls, href: str) -> Page | None:
        normalized = normalize_docs_href(href)
        if normalized is None:
            return None
        slug = normalized.removeprefix(DOCS_PREFIX)
        return cls(
            url=f"{BASE_URL}{normalized}",
            href=normalized,
            output=OUTPUT_ROOT / f"{slug}.md",
        )

    @property
    def markdown_url(self) -> str:
        return f"{self.url}.md"


def refresh() -> list[Path]:
    outputs: list[Path] = []
    seen: set[Path] = set()
    for page in discover_pages():
        if page.output in seen:
            raise RuntimeError(f"duplicate output path: {page.output}")
        seen.add(page.output)
        outputs.append(write_page(page))
    return outputs


def discover_pages() -> list[Page]:
    seed = Page.from_href(DISCOVERY_SEED)
    if seed is None:
        raise RuntimeError(f"invalid Claude docs discovery seed: {DISCOVERY_SEED}")

    pages: dict[str, Page] = {seed.href: seed}
    queue = [seed]
    visited: set[str] = set()

    while queue:
        page = queue.pop(0)
        if page.href in visited:
            continue
        visited.add(page.href)

        for discovered in discover_pages_from_html(fetch_text(page.url)):
            if discovered.href in pages:
                continue
            pages[discovered.href] = discovered
            queue.append(discovered)

    return list(pages.values())


def discover_pages_from_html(html: str) -> list[Page]:
    soup = BeautifulSoup(html, "html.parser")

    pages: dict[str, Page] = {}
    for anchor in soup.select('a[href^="/docs/en/"], a[href^="https://code.claude.com/docs/en/"]'):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        page = Page.from_href(href)
        if page is not None:
            pages.setdefault(page.href, page)
    return list(pages.values())


def normalize_docs_href(href: str) -> str | None:
    parsed = urlparse(href.split("#", 1)[0].strip())
    path = parsed.path.rstrip("/")
    if path.endswith(".md"):
        path = path.removesuffix(".md")
    if not path.startswith(DOCS_PREFIX):
        return None
    if path == DOCS_PREFIX.rstrip("/"):
        return None
    return path


def write_page(page: Page) -> Path:
    markdown = normalize_markdown(fetch_text(page.markdown_url))
    validate_markdown(page, markdown)
    page.output.parent.mkdir(parents=True, exist_ok=True)
    page.output.write_text(markdown, encoding="utf-8")
    return page.output


def normalize_markdown(markdown: str) -> str:
    markdown = strip_docs_index(markdown)
    markdown = normalize_admonitions(markdown)
    return markdown.strip() + "\n"


def strip_docs_index(markdown: str) -> str:
    return re.sub(
        r"\A> ## Documentation Index\n"
        r"> Fetch the complete documentation index at: .+\n"
        r"> Use this file to discover all available pages before exploring further\.\n\n",
        "",
        markdown,
    )


def normalize_admonitions(markdown: str) -> str:
    pattern = re.compile(
        r"<(Note|Tip|Important|Warning|Caution)(?:\s[^>]*)?>\n(.*?)\n</\1>",
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).upper()
        body = textwrap_admonition(match.group(2))
        return f"> [!{label}]\n{body}"

    return pattern.sub(replace, markdown)


def textwrap_admonition(body: str) -> str:
    lines = [line.strip() for line in body.strip().splitlines()]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def validate_markdown(page: Page, markdown: str) -> None:
    if len(markdown) < 200 or not markdown.lstrip().startswith("# "):
        raise RuntimeError(f"unexpectedly small Claude markdown for {page.url}")
    if "Documentation Index" in markdown:
        raise RuntimeError(f"Claude markdown contains documentation index: {page.url}")
    if markdown.lstrip().lower().startswith("<!doctype html"):
        raise RuntimeError(f"Claude markdown looks like HTML: {page.url}")
