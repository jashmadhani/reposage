"""Fetch a public GitHub issue (no auth) for Fix Plan mode."""

import re

import httpx

ISSUE_URL_RE = re.compile(
    r"^https://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)/?(?:[?#].*)?$"
)
MAX_BODY_CHARS = 4000
TIMEOUT_SECONDS = 10


class IssueError(ValueError):
    """Bad issue URL (400) or a failed GitHub lookup (502, see .upstream)."""

    def __init__(self, message: str, upstream: bool = False):
        super().__init__(message)
        self.upstream = upstream


def parse_issue_url(url: str) -> tuple[str, str, int]:
    m = ISSUE_URL_RE.match((url or "").strip())
    if not m:
        raise IssueError("Enter a GitHub issue URL like https://github.com/owner/name/issues/123")
    owner, name, number = m.groups()
    return owner, name, int(number)


def fetch_issue(url: str) -> dict:
    owner, name, number = parse_issue_url(url)
    api = f"https://api.github.com/repos/{owner}/{name}/issues/{number}"
    try:
        resp = httpx.get(
            api,
            timeout=TIMEOUT_SECONDS,
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.HTTPError as e:
        raise IssueError(f"Could not reach GitHub: {e}", upstream=True)
    if resp.status_code != 200:
        raise IssueError(f"GitHub returned {resp.status_code} for that issue.", upstream=True)
    data = resp.json()
    if "pull_request" in data:
        raise IssueError("That is a pull request, not an issue.")
    return {
        "title": data.get("title", ""),
        "body": (data.get("body") or "")[:MAX_BODY_CHARS],
        "url": url,
    }
