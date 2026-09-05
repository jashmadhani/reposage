"""Clone a public GitHub repo and collect its source files."""

import fnmatch
import os
import shutil

from git import Repo

# Where the clone lives. Wiped and rebuilt on every /index call.
CLONE_DIR = "temp_repo"

# Only files with these extensions are indexed.
INCLUDED_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb",
    ".md", ".txt", ".json", ".yaml", ".yml",
]

# Filename patterns that are never indexed, so secrets never reach the LLM.
EXCLUDED_FILE_PATTERNS = [
    ".env", ".env.*", "*.pem", "*.key", "id_rsa*", "credentials*", "secrets*",
]

# Directory names that are skipped entirely while walking.
EXCLUDED_DIRECTORIES = [
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
]

# Files bigger than this are skipped (bytes).
MAX_FILE_SIZE_BYTES = 100 * 1024


def clone_repo(repo_url):
    """Delete any previous clone, then clone repo_url fresh. Returns (path, name)."""
    if os.path.exists(CLONE_DIR):
        shutil.rmtree(CLONE_DIR)
    Repo.clone_from(repo_url, CLONE_DIR, depth=1)
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    return CLONE_DIR, repo_name


def is_excluded_file(filename):
    """True if the filename matches any pattern on the exclusion list."""
    for pattern in EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def collect_files(repo_path):
    """Walk the clone and return [(relative_path, file_text), ...]."""
    collected = []

    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Mutating dirnames in place stops os.walk from descending into them.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRECTORIES]

        for filename in filenames:
            if is_excluded_file(filename):
                continue
            if os.path.splitext(filename)[1] not in INCLUDED_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, filename)
            if os.path.getsize(full_path) > MAX_FILE_SIZE_BYTES:
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue

            if not text.strip():
                continue

            relative_path = os.path.relpath(full_path, repo_path)
            collected.append((relative_path, text))

    return collected
