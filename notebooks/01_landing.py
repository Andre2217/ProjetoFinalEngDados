# Databricks notebook source

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE_URL = "https://hacker-news.firebaseio.com/v0"

LANDING_DIR = Path(
    "/Volumes/hackernews/hacker_news/data/landing"
)


def collect_hacker_news_landing(story_limit: int = 30) -> str:
    collected_at = datetime.now(timezone.utc)

    response = requests.get(
        f"{BASE_URL}/topstories.json",
        timeout=30,
    )

    response.raise_for_status()

    story_ids = response.json()[:story_limit]

    output_dir = (
        LANDING_DIR
        / collected_at.strftime("%Y")
        / collected_at.strftime("%m")
        / collected_at.strftime("%d")
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"hacker_news_{collected_at.strftime('%H%M%S')}.ndjson"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for rank, story_id in enumerate(
            story_ids,
            start=1,
        ):
            item_response = requests.get(
                f"{BASE_URL}/item/{story_id}.json",
                timeout=30,
            )

            item_response.raise_for_status()

            record = {
                "collected_at": collected_at.isoformat(),
                "source": "hacker_news_firebase_api",
                "list_type": "topstories",
                "rank": rank,
                "story_id": story_id,
                "item": item_response.json(),
            }

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    return str(output_path)


output_path = collect_hacker_news_landing(
    story_limit=30
)

print(output_path)