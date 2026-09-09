from typing import Any

import requests

from src.config import HACKER_NEWS_BASE_URL, REQUEST_TIMEOUT_SECONDS


class HackerNewsClient:
    allowed_story_lists = {"topstories", "newstories", "beststories"}

    def __init__(
        self,
        base_url: str = HACKER_NEWS_BASE_URL,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def get_story_ids(self, list_type: str = "topstories") -> list[int]:
        if list_type not in self.allowed_story_lists:
            raise ValueError(f"Lista não suportada: {list_type}")

        response = self.session.get(
            f"{self.base_url}/{list_type}.json",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        story_ids = response.json()
        if not isinstance(story_ids, list):
            raise ValueError("Resposta inesperada ao consultar a lista de histórias.")

        return [int(story_id) for story_id in story_ids]

    def get_item(self, story_id: int) -> dict[str, Any] | None:
        response = self.session.get(
            f"{self.base_url}/item/{story_id}.json",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        item = response.json()
        if item is None:
            return None
        if not isinstance(item, dict):
            raise ValueError(f"Resposta inesperada para o item {story_id}.")

        return item

    def collect_stories(
        self,
        limit: int,
        list_type: str = "topstories",
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("O limite precisa ser maior que zero.")

        story_ids = self.get_story_ids(list_type=list_type)[:limit]
        stories = []

        for rank, story_id in enumerate(story_ids, start=1):
            stories.append(
                {
                    "rank": rank,
                    "story_id": story_id,
                    "payload": self.get_item(story_id),
                }
            )

        return stories
