import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://hacker-news.firebaseio.com/v0"
LANDING_DIR = Path("/opt/airflow/project/data/landing")


def collect_hacker_news_landing(story_limit: int = 30) -> str:
    collected_at = datetime.now(timezone.utc)

    topstories_response = requests.get(
        f"{BASE_URL}/topstories.json",
        timeout=30,
    )
    topstories_response.raise_for_status()
    story_ids = topstories_response.json()[:story_limit]

    items = []
    for story_id in story_ids:
        item_response = requests.get(
            f"{BASE_URL}/item/{story_id}.json",
            timeout=30,
        )
        item_response.raise_for_status()
        items.append(item_response.json())

    snapshot = {
        "collected_at": collected_at.isoformat(),
        "source": "hacker_news_firebase_api",
        "list_type": "topstories",
        "story_ids": story_ids,
        "items": items,
    }

    output_dir = LANDING_DIR / collected_at.strftime("%Y/%m/%d")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"hacker_news_{collected_at.strftime('%H%M%S')}.json"
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(output_path)
