from datetime import datetime

import pandas as pd

from src.quality.validations import split_valid_and_rejected


def build_valid_record():
    now = datetime.utcnow()
    return {
        "snapshot_id": "snapshot-1",
        "story_id": 123,
        "collected_at": now,
        "list_type": "topstories",
        "rank": 1,
        "title": "Example story",
        "author": "author",
        "url": "https://example.com/story",
        "domain": "example.com",
        "score": 10,
        "comments_count": 5,
        "published_at": now,
        "item_type": "story",
        "is_deleted": False,
        "is_dead": False,
    }


def test_valid_record_is_accepted():
    dataframe = pd.DataFrame([build_valid_record()])

    valid, rejected = split_valid_and_rejected(dataframe)

    assert len(valid) == 1
    assert rejected.empty


def test_invalid_rank_is_rejected():
    record = build_valid_record()
    record["rank"] = 0
    dataframe = pd.DataFrame([record])

    valid, rejected = split_valid_and_rejected(dataframe)

    assert valid.empty
    assert len(rejected) == 1
    assert "rank" in rejected.iloc[0]["validation_errors"]
