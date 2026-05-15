from __future__ import annotations

from tools.docs.scrape import codex


def test_codex_markdown_endpoint_matches_copy_button() -> None:
    page = codex.Page.from_href("/codex/guides/agents-md")

    assert page is not None
    assert page.markdown_url == "https://developers.openai.com/codex/guides/agents-md.md"


def test_validates_expected_codex_markdown() -> None:
    page = codex.Page.from_href("/codex/guides/agents-md")
    markdown = "\n".join(
        [
            "# Custom instructions with AGENTS.md",
            "## How Codex discovers guidance",
            "## Create global guidance",
            "## Layer project instructions",
            "## Customize fallback filenames",
            "## Verify your setup",
            "## Troubleshoot discovery issues",
        ]
    )

    assert page is not None
    codex.validate_markdown(page, markdown)


def test_discovers_codex_configuration_pages_from_left_nav() -> None:
    pages = codex.discover_pages_from_html(
        """<nav data-left-nav-id="/codex">
        <div>
          <h3>Getting Started</h3>
          <ul><li><a href="/codex/quickstart">Quickstart</a></li></ul>
        </div>
        <div>
          <h3>Configuration</h3>
          <ul>
            <li><a href="/codex/config-basic">Config Basics</a></li>
            <li><a href="/codex/guides/agents-md">AGENTS.md</a></li>
            <li><a href="/codex/plugins/build">Build plugins</a></li>
          </ul>
        </div>
        </nav>"""
    )

    assert [page.href for page in pages] == [
        "/codex/config-basic",
        "/codex/guides/agents-md",
        "/codex/plugins/build",
    ]
    assert pages[2].output == codex.OUTPUT_ROOT / "plugins" / "build.md"
