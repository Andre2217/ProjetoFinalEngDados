from pathlib import Path

from prefect import flow, task

from src.bronze.bronze_writer import BronzeWriter
from src.config import DEFAULT_STORY_LIMIT
from src.ingestion.hacker_news_client import HackerNewsClient
from src.silver.silver_transformer import SilverTransformer


@task(retries=3, retry_delay_seconds=10)
def collect_stories_task(limit: int, list_type: str) -> list[dict]:
    client = HackerNewsClient()
    return client.collect_stories(limit=limit, list_type=list_type)


@task
def write_bronze_task(stories: list[dict], list_type: str) -> dict:
    snapshot = BronzeWriter().write_snapshot(stories, list_type=list_type)
    return {
        "snapshot_id": snapshot.snapshot_id,
        "collected_at": snapshot.collected_at,
        "file_path": str(snapshot.file_path),
        "records_written": snapshot.records_written,
    }


@task
def process_silver_task(bronze_result: dict) -> dict:
    transformer = SilverTransformer()
    return transformer.process_bronze_file(Path(bronze_result["file_path"]))


@flow(name="hacker-news-bronze-silver")
def run_pipeline(
    limit: int = DEFAULT_STORY_LIMIT,
    list_type: str = "topstories",
) -> dict:
    stories = collect_stories_task(limit=limit, list_type=list_type)
    bronze_result = write_bronze_task(stories, list_type=list_type)
    silver_result = process_silver_task(bronze_result)

    return {
        **bronze_result,
        **silver_result,
    }


if __name__ == "__main__":
    print(run_pipeline())
