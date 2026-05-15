from __future__ import annotations

from tools.docs.scrape import claude


def test_strips_claude_docs_index() -> None:
    markdown = claude.normalize_markdown(
        """> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Configure permissions
"""
    )

    assert "Documentation Index" not in markdown
    assert markdown.startswith("# Configure permissions")


def test_normalizes_claude_admonition_tags() -> None:
    markdown = claude.normalize_markdown(
        """# Page

<Warning title="Security">
  Use isolated environments.
</Warning>
"""
    )

    assert "> [!WARNING]\n> Use isolated environments." in markdown


def test_claude_markdown_urls_append_md() -> None:
    page = claude.Page.from_href("https://code.claude.com/docs/en/permissions.md")

    assert page is not None
    assert page.markdown_url == "https://code.claude.com/docs/en/permissions.md"


def test_discovers_claude_pages_from_sidebar_html() -> None:
    pages = claude.discover_pages_from_html(
        """<div id="navigation-items">
        <a href="/docs/en/cli-reference">CLI reference</a>
        <a href="/docs/en/agent-sdk/overview">Agent SDK</a>
        <a href="/docs/en/memory#auto-memory">Memory</a>
        <a href="/docs/fr/overview">French</a>
        </div>"""
    )

    assert [page.href for page in pages] == [
        "/docs/en/cli-reference",
        "/docs/en/agent-sdk/overview",
        "/docs/en/memory",
    ]
    assert pages[1].output == claude.OUTPUT_ROOT / "agent-sdk" / "overview.md"


def test_claude_validation_allows_html_examples() -> None:
    page = claude.Page.from_href("/docs/en/skills")

    assert page is not None
    claude.validate_markdown(
        page,
        """# Extend Claude with skills

```html
<!DOCTYPE html>
<html></html>
```

This page contains enough text to behave like a normal markdown reference page.
This page contains enough text to behave like a normal markdown reference page.
This page contains enough text to behave like a normal markdown reference page.
""",
    )
