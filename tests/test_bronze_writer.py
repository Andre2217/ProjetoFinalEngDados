import json

from src.bronze.bronze_writer import BronzeWriter


def test_write_snapshot_creates_ndjson(tmp_path):
    stories = [
        {
            "rank": 1,
            "story_id": 123,
            "payload": {"id": 123, "title": "Example", "score": 10},
        }
    ]

    result = BronzeWriter(base_dir=tmp_path).write_snapshot(
        stories,
        list_type="topstories",
    )

    assert result.file_path.exists()
    assert result.records_written == 1

    record = json.loads(result.file_path.read_text(encoding="utf-8").strip())
    assert record["story_id"] == 123
    assert record["payload"]["title"] == "Example"
    assert record["list_type"] == "topstories"
