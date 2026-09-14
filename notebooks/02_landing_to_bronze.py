from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
)


LANDING_PATH = "/Volumes/hackernews/hacker_news/data/landing"


QUALITY_RULES = {
    "story_id_valido":
        "story_id IS NOT NULL AND story_id > 0",

    "story_id_confere_com_item":
        "item_id IS NOT NULL AND story_id = item_id",

    "data_coleta_valida":
        "collected_at IS NOT NULL",

    "rank_valido":
        "rank IS NOT NULL AND rank BETWEEN 1 AND 500",

    "titulo_valido":
        "title IS NOT NULL AND LENGTH(TRIM(title)) > 0",

    "score_valido":
        "score IS NOT NULL AND score >= 0",

    "comentarios_validos":
        "comments IS NOT NULL AND comments >= 0",

    "data_publicacao_valida":
        "published_at IS NOT NULL",

    "fonte_valida":
        "COALESCE(source = 'hacker_news_firebase_api', FALSE)",

    "tipo_lista_valido":
        "COALESCE(list_type = 'topstories', FALSE)",

    "tipo_item_valido":
        "COALESCE(item_type = 'story', FALSE)",

    "registro_ativo":
        "is_dead = FALSE AND is_deleted = FALSE",

    "schema_valido":
        "_rescued_data IS NULL",

    "json_valido":
        "_corrupt_record IS NULL",
}


item_schema = StructType(
    [
        StructField("id", LongType(), True),
        StructField("by", StringType(), True),
        StructField("descendants", LongType(), True),
        StructField("kids", ArrayType(LongType()), True),
        StructField("score", LongType(), True),
        StructField("time", LongType(), True),
        StructField("title", StringType(), True),
        StructField("type", StringType(), True),
        StructField("url", StringType(), True),
        StructField("text", StringType(), True),
        StructField("dead", BooleanType(), True),
        StructField("deleted", BooleanType(), True),
    ]
)


landing_schema = StructType(
    [
        StructField("collected_at", StringType(), True),
        StructField("source", StringType(), True),
        StructField("list_type", StringType(), True),
        StructField("rank", LongType(), True),
        StructField("story_id", LongType(), True),
        StructField("item", item_schema, True),
        StructField("_corrupt_record", StringType(), True),
    ]
)


def add_quality_columns(dataframe):
    error_expressions = [
        F.when(
            ~F.expr(
                f"COALESCE(({condition}), FALSE)"
            ),
            F.lit(rule_name),
        )
        for rule_name, condition in QUALITY_RULES.items()
    ]

    return (
        dataframe
        .withColumn(
            "quality_errors",
            F.array_compact(
                F.array(*error_expressions)
            ),
        )
        .withColumn(
            "is_quarantined",
            F.size("quality_errors") > 0,
        )
    )


@dp.temporary_view()
def landing_prepared():
    landing_df = (
        spark.readStream
        .format("cloudFiles")
        .schema(landing_schema)
        .option("cloudFiles.format", "json")
        .option(
            "cloudFiles.schemaEvolutionMode",
            "rescue",
        )
        .option(
            "rescuedDataColumn",
            "_rescued_data",
        )
        .option(
            "pathGlobFilter",
            "*.ndjson",
        )
        .option(
            "mode",
            "PERMISSIVE",
        )
        .option(
            "columnNameOfCorruptRecord",
            "_corrupt_record",
        )
        .load(LANDING_PATH)
    )

    return (
        landing_df
        .select(
            F.to_timestamp(
                "collected_at"
            ).alias("collected_at"),

            F.lower(
                F.trim("source")
            ).alias("source"),

            F.lower(
                F.trim("list_type")
            ).alias("list_type"),

            F.col("rank")
            .cast("int")
            .alias("rank"),

            F.col("story_id")
            .cast("long")
            .alias("story_id"),

            F.col("item.id")
            .cast("long")
            .alias("item_id"),

            F.trim(
                F.col("item.title")
            ).alias("title"),

            F.trim(
                F.col("item.by")
            ).alias("author"),

            F.col("item.url")
            .alias("url"),

            F.col("item.text")
            .alias("text"),

            F.col("item.score")
            .cast("int")
            .alias("score"),

            F.coalesce(
                F.col("item.descendants"),
                F.lit(0),
            )
            .cast("int")
            .alias("comments"),

            F.to_timestamp(
                F.from_unixtime(
                    F.col("item.time")
                )
            ).alias("published_at"),

            F.lower(
                F.trim(
                    F.col("item.type")
                )
            ).alias("item_type"),

            F.lower(
                F.regexp_extract(
                    F.col("item.url"),
                    r"^(?:https?://)?(?:www\.)?([^/:]+)",
                    1,
                )
            ).alias("domain"),

            F.coalesce(
                F.col("item.dead"),
                F.lit(False),
            ).alias("is_dead"),

            F.coalesce(
                F.col("item.deleted"),
                F.lit(False),
            ).alias("is_deleted"),

            F.col("_rescued_data"),

            F.col("_corrupt_record"),

            F.col(
                "_metadata.file_path"
            ).alias("source_file"),

            F.col(
                "_metadata.file_modification_time"
            ).alias("source_file_modified_at"),
        )
        .withColumn(
            "record_key",
            F.sha2(
                F.concat_ws(
                    "|",
                    F.col("source_file"),
                    F.col("story_id").cast("string"),
                ),
                256,
            ),
        )
    )


@dp.table(
    name="landing_validated",
    temporary=True,
)
@dp.expect_all(QUALITY_RULES)
def landing_validated():
    dataframe = spark.readStream.table(
        "landing_prepared"
    )

    return add_quality_columns(
        dataframe
    )


@dp.table(
    name="bronze_stories",
    comment="Registros válidos provenientes da Landing do Hacker News.",
)
def bronze_stories():
    return (
        spark.readStream
        .table("landing_validated")
        .filter(
            F.col("is_quarantined") == False
        )
        .select(
            "record_key",
            "collected_at",
            "source",
            "list_type",
            "rank",
            "story_id",
            "title",
            "author",
            "url",
            "domain",
            "text",
            "score",
            "comments",
            "published_at",
            "item_type",
            "source_file",
            "source_file_modified_at",
        )
        .withColumn(
            "bronze_loaded_at",
            F.current_timestamp(),
        )
    )


@dp.table(
    name="quarantine_stories",
    comment="Registros rejeitados pelas regras de qualidade da Landing.",
)
def quarantine_stories():
    return (
        spark.readStream
        .table("landing_validated")
        .filter(
            F.col("is_quarantined") == True
        )
        .select(
            "record_key",
            "collected_at",
            "source",
            "list_type",
            "rank",
            "story_id",
            "item_id",
            "title",
            "author",
            "url",
            "domain",
            "text",
            "score",
            "comments",
            "published_at",
            "item_type",
            "is_dead",
            "is_deleted",
            "_rescued_data",
            "_corrupt_record",
            "quality_errors",
            "source_file",
            "source_file_modified_at",
        )
        .withColumn(
            "quarantined_at",
            F.current_timestamp(),
        )
    )


# JOBS:
# Depois configure no Lakeflow Jobs:
#
# Task 1 -> 01_landing.py
# Task 2 -> executar este Lakeflow Pipeline
#
# Dependência:
# Task 2 somente executa após sucesso da Task 1.
#
# Sugestão:
# agendamento = 30 minutos
# retries = 2