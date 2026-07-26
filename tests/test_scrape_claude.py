from __future__ import annotations

from email.message import Message
from typing import Self
from urllib.error import HTTPError, URLError

import pytest

from tools.docs.scrape import claude
from tools.docs.scrape import fetch as fetch_module


class Response:
    status = 200
    headers = Message()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b"# Claude docs"


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


def test_fetch_retries_transient_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    timeout = URLError(TimeoutError("handshake timed out"))
    results = iter([timeout, timeout, Response()])
    delays: list[int] = []

    def urlopen(*args: object, **kwargs: object) -> Response:
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(fetch_module, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module, "sleep", delays.append)

    assert fetch_module.fetch_text("https://code.claude.com/docs/test.md") == "# Claude docs"
    assert delays == [1, 2]
    assert capsys.readouterr().out.splitlines() == [
        "Fetching https://code.claude.com/docs/test.md",
        "Retrying (2/3) https://code.claude.com/docs/test.md",
        "Retrying (3/3) https://code.claude.com/docs/test.md",
    ]


def test_fetch_retries_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    results = iter(
        [
            HTTPError("https://example.com", 503, "unavailable", Message(), None),
            Response(),
        ]
    )
    delays: list[int] = []

    def urlopen(*args: object, **kwargs: object) -> Response:
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(fetch_module, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module, "sleep", delays.append)

    assert fetch_module.fetch_text("https://example.com") == "# Claude docs"
    assert delays == [1]


def test_fetch_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    delays: list[int] = []

    def urlopen(*args: object, **kwargs: object) -> Response:
        nonlocal calls
        calls += 1
        raise HTTPError("https://example.com", 404, "not found", Message(), None)

    monkeypatch.setattr(fetch_module, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module, "sleep", delays.append)

    with pytest.raises(HTTPError) as error:
        fetch_module.fetch_text("https://example.com")

    assert error.value.code == 404
    assert calls == 1
    assert delays == []


def test_normalizes_claude_index_as_readme() -> None:
    assert claude.normalize_index("# Claude Code Docs\n") == (
        "# Claude Code Docs\n\nSource: <https://code.claude.com/docs/llms.txt>\n"
    )


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
