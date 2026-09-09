import pandera.pandas as pa
from pandera import Check


silver_story_schema = pa.DataFrameSchema(
    {
        "snapshot_id": pa.Column(str, nullable=False),
        "story_id": pa.Column(int, Check.gt(0), nullable=False, coerce=True),
        "collected_at": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "list_type": pa.Column(
            str,
            Check.isin(["topstories", "newstories", "beststories"]),
            nullable=False,
        ),
        "rank": pa.Column(int, Check.ge(1), nullable=False, coerce=True),
        "title": pa.Column(str, Check.str_length(min_value=1), nullable=False),
        "author": pa.Column(str, nullable=True),
        "url": pa.Column(str, nullable=True),
        "domain": pa.Column(str, nullable=True),
        "score": pa.Column(int, Check.ge(0), nullable=False, coerce=True),
        "comments_count": pa.Column(int, Check.ge(0), nullable=False, coerce=True),
        "published_at": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "item_type": pa.Column(str, nullable=False),
        "is_deleted": pa.Column(bool, nullable=False, coerce=True),
        "is_dead": pa.Column(bool, nullable=False, coerce=True),
    },
    strict=True,
    coerce=True,
)
