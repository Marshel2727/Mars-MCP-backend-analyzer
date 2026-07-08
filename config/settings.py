import os
from pathlib import Path

try:
  from dotenv import load_dotenv
except ModuleNotFoundError:
  load_dotenv = None


APP_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv:
  load_dotenv(APP_ROOT / ".env")

IGNORE_PATTERNS_FILE = APP_ROOT / "config" / "ignore_patterns.json"

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "300000"))

MAX_CONTEXT_FILES = int(os.getenv("MAX_CONTEXT_FILES", "80"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))

OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "30000"))

OLLAMA_NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "999"))

OLLAMA_MAIN_GPU = int(os.getenv("OLLAMA_MAIN_GPU", "0"))

OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))

OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))

OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))

OLLAMA_REPEAT_PENALTY = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.1"))

OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "0")

ALLOWED_EXTENSIONS = {
    ".py",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".ini",
    ".cfg",
    ".sql",
    ".yml",
    ".yaml",
}

ALLOWED_FILENAMES = {
    "Dockerfile",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "alembic.ini",
    ".env.example",
    "mars",
    "mars-mcp",
    "Makefile",
}
