from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .fetch import fetch_text

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "https://developers.openai.com"
DOCS_PREFIX = "/codex/"
DISCOVERY_URL = f"{BASE_URL}/codex/llms.txt"
OUTPUT_ROOT = ROOT / "docs" / "reference" / "codex"
INDEX_OUTPUT = OUTPUT_ROOT / "README.md"
AGENTS_MD_HEADINGS = [
    "How Codex discovers guidance",
    "Create global guidance",
    "Layer project instructions",
    "Customize fallback filenames",
    "Verify your setup",
    "Troubleshoot discovery issues",
]
NAV_NOISE = {
    "Search docs",
    "Primary navigation",
}

# Match Codex's absolute markdown links in the machine-readable docs index.
DOCS_LINK_PATTERN = re.compile(r"https://developers\.openai\.com/codex/[A-Za-z0-9_./-]+\.md")


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
    index = fetch_text(DISCOVERY_URL)
    outputs = [write_index(index)]
    seen: set[Path] = set()
    for page in discover_pages_from_index(index):
        if page.output in seen:
            raise RuntimeError(f"duplicate output path: {page.output}")
        seen.add(page.output)
        outputs.append(write_page(page))
    return outputs


def discover_pages() -> list[Page]:
    return discover_pages_from_index(fetch_text(DISCOVERY_URL))


def write_index(index: str) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_OUTPUT.write_text(normalize_index(index), encoding="utf-8")
    return INDEX_OUTPUT


def normalize_index(index: str) -> str:
    return f"{index.strip()}\n\nSource: <{DISCOVERY_URL}>\n"


def discover_pages_from_index(index: str) -> list[Page]:
    pages: dict[str, Page] = {}
    for href in DOCS_LINK_PATTERN.findall(index):
        page = Page.from_href(href)
        if page is not None:
            pages.setdefault(page.href, page)

    if not pages:
        raise RuntimeError("Codex docs index contained no pages")
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
    markdown = fetch_text(page.markdown_url)
    validate_markdown(page, markdown)
    page.output.parent.mkdir(parents=True, exist_ok=True)
    page.output.write_text(markdown.strip() + "\n", encoding="utf-8")
    return page.output


def validate_markdown(page: Page, markdown: str) -> None:
    if len(markdown) < 200 or not markdown.lstrip().startswith("# "):
        raise RuntimeError(f"unexpectedly small Codex markdown for {page.url}")
    for phrase in NAV_NOISE:
        if phrase in markdown:
            raise RuntimeError(f"Codex markdown contains navigation noise: {phrase}")
    if markdown.lstrip().lower().startswith("<!doctype html"):
        raise RuntimeError(f"Codex markdown looks like HTML: {page.url}")
    if page.href == "/codex/guides/agents-md":
        for heading in AGENTS_MD_HEADINGS:
            if heading not in markdown:
                raise RuntimeError(f"missing expected Codex heading: {heading}")
