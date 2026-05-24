from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .fetch import fetch_text

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "https://code.claude.com"
DOCS_PREFIX = "/docs/en/"
OUTPUT_ROOT = ROOT / "docs" / "reference" / "claude"
DISCOVERY_URL = f"{BASE_URL}/docs/llms.txt"
INDEX_OUTPUT = OUTPUT_ROOT / "README.md"

# Match Claude's absolute markdown links in the machine-readable docs index.
DOCS_LINK_PATTERN = re.compile(r"https://code\.claude\.com/docs/en/[A-Za-z0-9_./-]+\.md")


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
        raise RuntimeError("Claude docs index contained no pages")
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
    # Remove the machine-readable index banner copied into individual markdown pages.
    return re.sub(
        r"\A> ## Documentation Index\n"
        r"> Fetch the complete documentation index at: .+\n"
        r"> Use this file to discover all available pages before exploring further\.\n\n",
        "",
        markdown,
    )


def normalize_admonitions(markdown: str) -> str:
    # Convert Claude custom admonition tags into GitHub-style blockquotes.
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
