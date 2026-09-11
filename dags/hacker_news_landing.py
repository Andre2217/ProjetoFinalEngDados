from datetime import datetime

from airflow.sdk import dag, task

from src.landing import collect_hacker_news_landing


@dag(
    dag_id="hacker_news_landing",
    schedule="*/30 * * * *",
    start_date=datetime(2026, 9, 10),
    catchup=False,
    tags=["hacker-news", "landing"],
)
def hacker_news_landing():
    @task(retries=2)
    def collect():
        return collect_hacker_news_landing(story_limit=30)

    collect()


hacker_news_landing()
