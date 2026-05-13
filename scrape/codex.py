from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scrape.fetch import fetch_text


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://developers.openai.com"
DOCS_PREFIX = "/codex/"
DISCOVERY_URL = f"{BASE_URL}/codex"
NAV_GROUP = "Configuration"
OUTPUT_ROOT = ROOT / "refs" / "codex"
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
    return discover_pages_from_html(fetch_text(DISCOVERY_URL))


def discover_pages_from_html(html: str, group_title: str = NAV_GROUP) -> list[Page]:
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one('nav[data-left-nav-id="/codex"]')
    if nav is None:
        raise RuntimeError("Codex left navigation not found")

    group = find_nav_group(nav, group_title)
    pages: dict[str, Page] = {}
    for anchor in group.select('a[href^="/codex/"], a[href^="https://developers.openai.com/codex/"]'):
        page = Page.from_href(anchor.get("href", ""))
        if page is not None:
            pages.setdefault(page.href, page)
    return list(pages.values())


def find_nav_group(nav: BeautifulSoup, title: str):
    for heading in nav.find_all("h3"):
        if heading.get_text(strip=True) == title:
            group = heading.find_parent("div")
            if group is None:
                break
            return group
    raise RuntimeError(f"Codex left navigation group not found: {title}")


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
