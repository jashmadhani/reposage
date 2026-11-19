"""Parse `path:start-end` Citations out of model text and turn them into
GitHub links. Only Citations whose path exists in the index are kept."""

import re

CITATION_RE = re.compile(r"([\w./-]+):(\d+)-(\d+)")


def parse_citations(text: str) -> list[tuple[str, int, int]]:
    """Return unique (path, start, end) tuples in order of first appearance."""
    seen = set()
    found = []
    for path, start, end in CITATION_RE.findall(text or ""):
        item = (path, int(start), int(end))
        if item not in seen:
            seen.add(item)
            found.append(item)
    return found


def github_url(repo_url: str, path: str, start: int, end: int) -> str:
    base = repo_url.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/blob/HEAD/{path}#L{start}-L{end}"


def resolve(text: str, index, repo_url: str) -> list[dict]:
    """Citations whose path is in the index, with links. `verified` is True
    when the range is non-empty and inside the file."""
    out = []
    for path, start, end in parse_citations(text):
        if path not in index.files:
            continue
        total = len(index.files[path].splitlines())
        verified = 1 <= start <= end <= total
        out.append(
            {
                "path": path,
                "start": start,
                "end": end,
                "url": github_url(repo_url, path, start, end),
                "verified": verified,
            }
        )
    return out
