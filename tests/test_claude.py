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


def test_discovers_claude_pages_from_llms_index() -> None:
    pages = claude.discover_pages_from_index(
        """# Claude Code Docs
        - [CLI reference](https://code.claude.com/docs/en/cli-reference.md): CLI docs.
        - [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview.md): SDK docs.
        - [Memory](https://code.claude.com/docs/en/memory.md): Memory docs.
        - [French](https://code.claude.com/docs/fr/overview.md): French docs.
        """
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
