import json
from pathlib import Path

from config.settings import IGNORE_PATTERNS_FILE


DEFAULT_PATTERNS = {
    "ignore_dirs": [
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".turbo",
        ".vite",
        "coverage",
        "out",
    ],
    "ignore_files": [
        ".env",
        ".DS_Store",
        "Thumbs.db",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ],
    "ignore_extensions": [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".svg",
        ".exe",
        ".dll",
        ".zip",
        ".rar",
        ".7z",
        ".pdf",
        ".mp4",
        ".mp3",
        ".pyc",
        ".pyo",
        ".log",
        ".tmp",
        ".db",
        ".sqlite",
        ".sqlite3",
    ],
}


def load_ignore_patterns() -> dict:
    if not IGNORE_PATTERNS_FILE.exists():
        return DEFAULT_PATTERNS

    try:
        with open(IGNORE_PATTERNS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return DEFAULT_PATTERNS


class IgnoreRules:
    def __init__(self):
        patterns = load_ignore_patterns()

        self.ignore_dirs = {item.lower() for item in patterns.get("ignore_dirs", [])}
        self.ignore_files = {item.lower() for item in patterns.get("ignore_files", [])}
        self.ignore_extensions = {
            item.lower() for item in patterns.get("ignore_extensions", [])
        }

    def should_ignore(self, path: Path) -> bool:
        path = Path(path)

        path_name = path.name.lower()
        path_suffix = path.suffix.lower()
        path_parts = {part.lower() for part in path.parts}

        if path_name in self.ignore_dirs:
            return True

        if path_name in self.ignore_files:
            return True

        if path_suffix in self.ignore_extensions:
            return True

        if path_parts.intersection(self.ignore_dirs):
            return True

        return False