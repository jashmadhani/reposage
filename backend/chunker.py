"""Split source files into retrievable chunks.

Whole-file embeddings dilute the signal of any single function, and the
embedding model silently truncates long inputs. So instead of one vector per
file we produce one vector per chunk:

* Python files are split on their top-level functions and classes using the
  standard library `ast` module, so a chunk is a real unit of code. Code that
  sits between definitions (imports, constants) becomes its own chunk.
* Everything else is split into fixed windows of lines with some overlap, so
  a function that straddles a boundary still appears whole in one window.
* Any chunk that is still too long is split again with the line window.

Every chunk keeps its file path and line range, which is what lets the agents
cite `path:start-end` in their answers.
"""

import ast
from dataclasses import dataclass

WINDOW_LINES = 60
OVERLAP_LINES = 15
MAX_CHUNK_LINES = 120
MIN_CHUNK_CHARS = 20


@dataclass(frozen=True)
class Chunk:
    path: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    symbol: str  # function/class name, or "" for windowed chunks
    text: str

    @property
    def citation(self) -> str:
        return f"{self.path}:{self.start_line}-{self.end_line}"

    def embedding_text(self) -> str:
        """Prefix the path (and symbol) so a query like 'auth middleware' can
        match on file names as well as code."""
        header = f"File: {self.path}"
        if self.symbol:
            header += f" | Symbol: {self.symbol}"
        return f"{header}\n{self.text}"


def _window(path, lines, offset=0, symbol=""):
    """Fixed-size overlapping line windows. `offset` is the 0-based line index
    of lines[0] within the original file."""
    chunks = []
    step = WINDOW_LINES - OVERLAP_LINES
    start = 0
    while start < len(lines):
        end = min(start + WINDOW_LINES, len(lines))
        text = "\n".join(lines[start:end])
        if len(text.strip()) >= MIN_CHUNK_CHARS:
            chunks.append(
                Chunk(path, offset + start + 1, offset + end, symbol, text)
            )
        if end == len(lines):
            break
        start += step
    return chunks


def _python_chunks(path, source, lines):
    """Split on top-level defs/classes. Returns None if the file doesn't parse,
    so the caller can fall back to windows."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None

    # (start_idx, end_idx_exclusive, symbol) for each top-level definition,
    # with decorators included in the span.
    spans = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans.append((first - 1, node.end_lineno, node.name))

    chunks = []
    cursor = 0
    for start, end, name in spans:
        if start > cursor:  # glue code between definitions
            chunks.extend(_window(path, lines[cursor:start], offset=cursor))
        body = lines[start:end]
        if len(body) > MAX_CHUNK_LINES:
            chunks.extend(_window(path, body, offset=start, symbol=name))
        else:
            text = "\n".join(body)
            if len(text.strip()) >= MIN_CHUNK_CHARS:
                chunks.append(Chunk(path, start + 1, end, name, text))
        cursor = end
    if cursor < len(lines):
        chunks.extend(_window(path, lines[cursor:], offset=cursor))
    return chunks


def chunk_file(path: str, text: str) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    if path.endswith(".py"):
        chunks = _python_chunks(path, text, lines)
        if chunks is not None:
            return chunks
    return _window(path, lines)


def chunk_files(files: list[tuple[str, str]]) -> list[Chunk]:
    chunks = []
    for path, text in files:
        chunks.extend(chunk_file(path, text))
    return chunks
