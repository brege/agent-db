from __future__ import annotations

import pytest

from tools.docs.scrape import codex


def test_codex_markdown_endpoint_matches_copy_button() -> None:
    page = codex.Page.from_href("/codex/guides/agents-md")

    assert page is not None
    assert page.markdown_url == "https://developers.openai.com/codex/guides/agents-md.md"


def test_validates_expected_codex_markdown() -> None:
    page = codex.Page.from_href("/codex/guides/agents-md")
    markdown = (
        "# Custom instructions with AGENTS.md\n"
        "## How Codex discovers guidance\n"
        "## Create global guidance\n"
        "## Layer project instructions\n"
        "## Customize fallback filenames\n"
        "## Verify your setup\n"
        "## Troubleshoot discovery issues"
    )

    assert page is not None
    codex.validate_markdown(page, markdown)


def test_validates_codex_manual_frontmatter() -> None:
    page = codex.Page.from_href("/codex/codex-manual")
    markdown = (
        '---\ntitle: "Codex Manual"\nhidden: true\n---\n\n'
        "## Find By Topic\n"
        "This manual contains enough text to behave like a normal reference page.\n"
        "This manual contains enough text to behave like a normal reference page.\n"
        "This manual contains enough text to behave like a normal reference page."
    )

    assert page is not None
    codex.validate_markdown(page, markdown)


def test_validates_short_codex_landing_page() -> None:
    page = codex.Page.from_href("/codex/app")
    markdown = '# ChatGPT desktop app\n\n<CodexSurfaceLanding surface="app" />\n'

    assert page is not None
    codex.validate_markdown(page, markdown)


def test_discovers_codex_pages_from_llms_index() -> None:
    pages = codex.discover_pages_from_index(
        """# Codex
        - [Config Basics](https://developers.openai.com/codex/config-basic.md): Config docs.
        - [AGENTS.md](https://developers.openai.com/codex/guides/agents-md.md): Agent docs.
        - [Build plugins](https://developers.openai.com/codex/plugins/build.md): Plugin docs.
        - [Combined Codex docs](https://developers.openai.com/codex/llms-full.txt): Full docs.
        """
    )

    assert [page.href for page in pages] == [
        "/codex/config-basic",
        "/codex/guides/agents-md",
        "/codex/plugins/build",
    ]
    assert pages[2].output == codex.OUTPUT_ROOT / "plugins" / "build.md"


@pytest.mark.parametrize("href", sorted(codex.NON_MARKDOWN_HREFS))
def test_ignores_non_markdown_codex_index_entries(href: str) -> None:
    assert codex.Page.from_href(f"https://developers.openai.com{href}.md") is None


def test_normalizes_codex_index_as_readme() -> None:
    assert codex.normalize_index("# Codex\n") == (
        "# Codex\n\nSource: <https://developers.openai.com/codex/llms.txt>\n"
    )
