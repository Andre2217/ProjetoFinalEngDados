import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
BRONZE_DIR = DATA_DIR / "bronze" / "hacker_news"
QUARANTINE_DIR = DATA_DIR / "quarantine"
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", DATA_DIR / "hacker_news.duckdb"))

HACKER_NEWS_BASE_URL = os.getenv(
    "HACKER_NEWS_BASE_URL",
    "https://hacker-news.firebaseio.com/v0",
)
DEFAULT_STORY_LIMIT = int(os.getenv("STORY_LIMIT", "30"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))


for directory in (BRONZE_DIR, QUARANTINE_DIR, DUCKDB_PATH.parent):
    directory.mkdir(parents=True, exist_ok=True)
