import json
from datetime import datetime, timezone

import duckdb

from src.silver.silver_transformer import SilverTransformer


def test_process_bronze_file_persists_silver_record(tmp_path):
    bronze_file = tmp_path / "snapshot.ndjson"
    database_path = tmp_path / "test.duckdb"
    quarantine_dir = tmp_path / "quarantine"

    record = {
        "snapshot_id": "snapshot-1",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "hacker_news",
        "list_type": "topstories",
        "rank": 1,
        "story_id": 123,
        "payload": {
            "id": 123,
            "title": "Example story",
            "by": "author",
            "url": "https://www.example.com/post",
            "score": 42,
            "descendants": 7,
            "time": 1700000000,
            "type": "story",
        },
    }
    bronze_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = SilverTransformer(
        database_path=database_path,
        quarantine_dir=quarantine_dir,
    ).process_bronze_file(bronze_file)

    assert result["records_valid"] == 1
    assert result["records_rejected"] == 0
    assert result["records_inserted"] == 1

    with duckdb.connect(str(database_path), read_only=True) as connection:
        row = connection.execute(
            """
            SELECT story_id, domain, score, comments_count
            FROM silver.story_snapshots
            """
        ).fetchone()

    assert row == (123, "example.com", 42, 7)
