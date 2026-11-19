"""Retrieval tools the agents call. ADK sends each function's name, signature
and docstring to the model, so the docstrings are written for the model."""

import fnmatch
import os

import vector_store
from citations import parse_citations

MAX_CHARS = 6000
MAX_LINES = 120
MAX_FILES = 200
NOT_INDEXED = "No repository is indexed."


def _truncate(text: str) -> str:
    # TOOL_MAX_CHARS lowers the cap for providers with small token budgets
    # (for example Groq's free tier, 8000 tokens per minute).
    limit = int(os.getenv("TOOL_MAX_CHARS", MAX_CHARS))
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def search_code(query: str) -> str:
    """Search the indexed repository for code related to the query.

    Args:
        query: What to look for, in plain words or identifiers.

    Returns:
        Up to 6 matching chunks. Each starts with a heading of the form
        path:start-end (symbol) and a score, followed by the code.
    """
    index = vector_store.current()
    if index is None:
        return NOT_INDEXED
    results = index.search(query)
    if not results:
        return "No relevant code found."
    blocks = []
    for chunk, score in results:
        symbol = f" ({chunk.symbol})" if chunk.symbol else ""
        blocks.append(f"### {chunk.citation}{symbol} score={score:.2f}\n{chunk.text}")
    return _truncate("\n\n".join(blocks))


def read_file_lines(path: str, start: int, end: int) -> str:
    """Read an exact range of lines from a file in the repository.

    Args:
        path: File path exactly as shown in search results.
        start: First line, 1 based.
        end: Last line, inclusive. At most 120 lines are returned.

    Returns:
        The lines, each prefixed with its line number, or an error message.
    """
    index = vector_store.current()
    if index is None:
        return NOT_INDEXED
    if path not in index.files:
        return f"Error: unknown path {path}"
    end = min(end, start + MAX_LINES - 1)
    text = index.read_lines(path, start, end)
    return _truncate(text) if text else "Error: empty line range"


def list_files(pattern: str = "*") -> str:
    """List file paths in the repository that match a glob pattern.

    Args:
        pattern: Glob such as *.py or src/*. Defaults to all files.

    Returns:
        One path per line, at most 200.
    """
    index = vector_store.current()
    if index is None:
        return NOT_INDEXED
    paths = sorted(p for p in index.files if fnmatch.fnmatch(p, pattern))
    if not paths:
        return "No files match."
    return _truncate("\n".join(paths[:MAX_FILES]))


def exit_loop(tool_context) -> str:
    """Approve the draft and finish. Call this only when every citation in the
    draft has been checked with read_file_lines and supports its claim.

    It refuses if the draft has no citation, or cites a file or line range
    that does not exist in the repository.
    """
    index = vector_store.current()
    draft = tool_context.state.get("draft", "")
    cites = parse_citations(draft)
    valid = []
    for path, start, end in cites:
        text = index.files.get(path) if index else None
        if text is not None and 1 <= start <= end <= len(text.splitlines()):
            valid.append((path, start, end))
    if not valid:
        return (
            "Not approved: the draft has no valid citation. Citations must be "
            "written path:start-end and point at lines that exist. Send the "
            "draft back to the Writer."
        )
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return "Approved."
