from pyspark import pipelines as dp
from pyspark.sql import functions as F

SILVER_COLUMNS = [
    "record_key",
    "collected_at",
    "rank",
    "story_id",
    "title",
    "author",
    "url",
    "domain",
    "score",
    "comments",
    "published_at",
    "source_file",
    "source_file_modified_at",
    "bronze_loaded_at",
]


TRIM_COLUMNS = [
    "title",
    "author",
    "url",
    "domain",
    "source_file",
]


COLUMN_TYPES = {
    "record_key": "string",
    "collected_at": "timestamp",
    "rank": "int",
    "story_id": "string",
    "title": "string",
    "author": "string",
    "url": "string",
    "domain": "string",
    "score": "int",
    "comments": "int",
    "published_at": "timestamp",
    "source_file": "string",
    "source_file_modified_at": "timestamp",
    "bronze_loaded_at": "timestamp",
}


# Checagens pós-cast: se algum cast falhar, o valor vira NULL
# e o registro é descartado (a métrica fica no Event Log)
SILVER_QUALITY_RULES = {
    "record_key_valido": "record_key IS NOT NULL",
    "story_id_valido": "story_id IS NOT NULL",
    "collected_at_valido": "collected_at IS NOT NULL",
    "rank_valido": "rank IS NOT NULL",
    "titulo_valido": "title IS NOT NULL",
    "published_at_valido": "published_at IS NOT NULL",
}


# ---------------------------------------------------------------------------
# Transformações genéricas
# ---------------------------------------------------------------------------

def select_columns(dataframe, columns):
    return dataframe.select(*columns)


def trim_columns(dataframe, columns):
    # Remove espaços do início e fim; string vazia vira NULL
    for column in columns:
        trimmed = F.trim(F.col(column))
        dataframe = dataframe.withColumn(
            column,
            F.when(trimmed == "", F.lit(None)).otherwise(trimmed),
        )
    return dataframe


def cast_columns(dataframe, column_types):
    for column, data_type in column_types.items():
        dataframe = dataframe.withColumn(
            column,
            F.col(column).cast(data_type),
        )
    return dataframe


# ---------------------------------------------------------------------------
# silver_story_snapshots
# Uma linha por story por coleta.
# ---------------------------------------------------------------------------

@dp.table(
    name="silver_story_snapshots",
comment="Top stories do Hacker News limpas e tipadas. Granularidade: uma linha por story em cada snapshot (chave: story_id + collected_at).",
)
@dp.expect_all_or_drop(SILVER_QUALITY_RULES)
def silver_story_snapshots():
    bronze = spark.readStream.table("bronze_stories")

    dataframe = select_columns(bronze, SILVER_COLUMNS)
    dataframe = trim_columns(dataframe, TRIM_COLUMNS)
    dataframe = cast_columns(dataframe, COLUMN_TYPES)

    return (
        dataframe
        # Protege contra reprocessamento do mesmo arquivo
        .dropDuplicates(["record_key"])
        .withColumn("silver_loaded_at", F.current_timestamp())
    )
