import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import BRONZE_DIR


@dataclass(frozen=True)
class BronzeSnapshot:
    snapshot_id: str
    collected_at: str
    file_path: Path
    records_written: int


class BronzeWriter:
    def __init__(self, base_dir: Path = BRONZE_DIR) -> None:
        self.base_dir = Path(base_dir)

    def write_snapshot(
        self,
        stories: list[dict[str, Any]],
        list_type: str,
    ) -> BronzeSnapshot:
        collected_at = datetime.now(timezone.utc)
        snapshot_id = str(uuid.uuid4())

        partition_dir = (
            self.base_dir
            / f"year={collected_at:%Y}"
            / f"month={collected_at:%m}"
            / f"day={collected_at:%d}"
        )
        partition_dir.mkdir(parents=True, exist_ok=True)

        file_name = (
            f"snapshot_{collected_at:%Y%m%dT%H%M%SZ}_{snapshot_id}.ndjson"
        )
        file_path = partition_dir / file_name
        collected_at_iso = collected_at.isoformat()

        with file_path.open("w", encoding="utf-8") as file:
            for story in stories:
                record = {
                    "snapshot_id": snapshot_id,
                    "collected_at": collected_at_iso,
                    "source": "hacker_news",
                    "list_type": list_type,
                    "rank": story["rank"],
                    "story_id": story["story_id"],
                    "payload": story["payload"],
                }
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

        return BronzeSnapshot(
            snapshot_id=snapshot_id,
            collected_at=collected_at_iso,
            file_path=file_path,
            records_written=len(stories),
        )
