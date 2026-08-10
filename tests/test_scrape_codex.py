from __future__ import annotations

import pytest

from tools.docs.scrape import codex


def test_codex_markdown_endpoint_matches_copy_button() -> None:
    page = codex.Page.from_href("/docs/agent-configuration/agents-md")

    assert page is not None
    assert page.markdown_url == "https://learn.chatgpt.com/docs/agent-configuration/agents-md.md"


def test_validates_expected_codex_markdown() -> None:
    page = codex.Page.from_href("/docs/agent-configuration/agents-md")
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
    page = codex.Page.from_href("/docs/codex-manual")
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
    page = codex.Page.from_href("/docs/app")
    markdown = '# ChatGPT desktop app\n\n<CodexSurfaceLanding surface="app" />\n'

    assert page is not None
    codex.validate_markdown(page, markdown)


def test_strips_docs_index_banner() -> None:
    markdown = (
        '---\ntitle: "Codex Manual"\nhidden: true\n---\n\n'
        "> For the complete documentation index, see "
        "[llms.txt](https://learn.chatgpt.com/llms.txt). Markdown versions of "
        "documentation pages are available by appending `.md` to the page URL.\n\n"
        "## Find By Topic\n"
    )

    assert codex.normalize_markdown(markdown) == (
        '---\ntitle: "Codex Manual"\nhidden: true\n---\n\n## Find By Topic\n'
    )


def test_discovers_codex_pages_from_llms_index() -> None:
    pages = codex.discover_pages_from_index(
        """# Codex
        - [Config Basics](https://learn.chatgpt.com/docs/config-file/config-basic.md): Config docs.
        - [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md): Agent docs.
        - [Best practices](https://learn.chatgpt.com/guides/best-practices.md): No markdown twin.
        - [Combined ChatGPT docs](https://learn.chatgpt.com/docs/llms-full.txt): Full docs.
        """
    )

    assert [page.href for page in pages] == [
        "/docs/config-file/config-basic",
        "/docs/agent-configuration/agents-md",
    ]
    assert pages[1].output == codex.OUTPUT_ROOT / "agent-configuration" / "agents-md.md"


@pytest.mark.parametrize("href", ["/guides/best-practices", "/resources", "/videos", "/docs"])
def test_ignores_hrefs_outside_docs_prefix(href: str) -> None:
    assert codex.Page.from_href(f"https://learn.chatgpt.com{href}.md") is None


def test_normalizes_codex_index_as_readme() -> None:
    assert codex.normalize_index("# Codex\n") == (
        "# Codex\n\nSource: <https://learn.chatgpt.com/llms.txt>\n"
    )
