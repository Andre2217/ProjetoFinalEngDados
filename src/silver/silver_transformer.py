import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import pandas as pd

from src.config import DUCKDB_PATH, QUARANTINE_DIR
from src.quality.validations import split_valid_and_rejected


class SilverTransformer:
    def __init__(
        self,
        database_path: Path = DUCKDB_PATH,
        quarantine_dir: Path = QUARANTINE_DIR,
    ) -> None:
        self.database_path = Path(database_path)
        self.quarantine_dir = Path(quarantine_dir)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def process_bronze_file(self, bronze_file_path: Path) -> dict[str, int | str]:
        dataframe = self._read_and_flatten(bronze_file_path)
        valid, rejected = split_valid_and_rejected(dataframe)

        rejected_count = self._write_quarantine(rejected)
        inserted_count = self._persist_valid_records(valid)

        return {
            "records_received": len(dataframe),
            "records_valid": len(valid),
            "records_rejected": rejected_count,
            "records_inserted": inserted_count,
            "database_path": str(self.database_path),
        }

    def _read_and_flatten(self, bronze_file_path: Path) -> pd.DataFrame:
        records = []

        with Path(bronze_file_path).open("r", encoding="utf-8") as file:
            for line in file:
                bronze_record = json.loads(line)
                payload = bronze_record.get("payload") or {}
                url = payload.get("url")

                records.append(
                    {
                        "snapshot_id": bronze_record.get("snapshot_id"),
                        "story_id": bronze_record.get("story_id"),
                        "collected_at": self._parse_iso_datetime(
                            bronze_record.get("collected_at")
                        ),
                        "list_type": bronze_record.get("list_type"),
                        "rank": bronze_record.get("rank"),
                        "title": payload.get("title"),
                        "author": payload.get("by"),
                        "url": url,
                        "domain": self._extract_domain(url),
                        "score": payload.get("score", 0),
                        "comments_count": payload.get("descendants", 0),
                        "published_at": self._from_unix_timestamp(
                            payload.get("time")
                        ),
                        "item_type": payload.get("type", "unknown"),
                        "is_deleted": bool(payload.get("deleted", False)),
                        "is_dead": bool(payload.get("dead", False)),
                    }
                )

        return pd.DataFrame(records)

    def _persist_valid_records(self, dataframe: pd.DataFrame) -> int:
        if dataframe.empty:
            return 0

        with duckdb.connect(str(self.database_path)) as connection:
            connection.execute("CREATE SCHEMA IF NOT EXISTS silver")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.story_snapshots (
                    snapshot_id VARCHAR NOT NULL,
                    story_id BIGINT NOT NULL,
                    collected_at TIMESTAMP NOT NULL,
                    list_type VARCHAR NOT NULL,
                    rank INTEGER NOT NULL,
                    title VARCHAR NOT NULL,
                    author VARCHAR,
                    url VARCHAR,
                    domain VARCHAR,
                    score BIGINT NOT NULL,
                    comments_count BIGINT NOT NULL,
                    published_at TIMESTAMP NOT NULL,
                    item_type VARCHAR NOT NULL,
                    is_deleted BOOLEAN NOT NULL,
                    is_dead BOOLEAN NOT NULL,
                    PRIMARY KEY (snapshot_id, story_id, list_type)
                )
                """
            )

            before_count = connection.execute(
                "SELECT COUNT(*) FROM silver.story_snapshots"
            ).fetchone()[0]

            connection.register("silver_batch", dataframe)
            connection.execute(
                """
                INSERT OR IGNORE INTO silver.story_snapshots
                SELECT
                    snapshot_id,
                    story_id,
                    collected_at,
                    list_type,
                    rank,
                    title,
                    author,
                    url,
                    domain,
                    score,
                    comments_count,
                    published_at,
                    item_type,
                    is_deleted,
                    is_dead
                FROM silver_batch
                """
            )

            after_count = connection.execute(
                "SELECT COUNT(*) FROM silver.story_snapshots"
            ).fetchone()[0]

        return after_count - before_count

    def _write_quarantine(self, dataframe: pd.DataFrame) -> int:
        if dataframe.empty:
            return 0

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_path = self.quarantine_dir / f"rejected_{timestamp}.ndjson"
        dataframe.to_json(
            file_path,
            orient="records",
            lines=True,
            force_ascii=False,
            date_format="iso",
        )
        return len(dataframe)

    @staticmethod
    def _extract_domain(url: str | None) -> str | None:
        if not url:
            return None
        domain = urlparse(url).netloc.lower()
        return domain.removeprefix("www.") or None

    @staticmethod
    def _from_unix_timestamp(value: int | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
