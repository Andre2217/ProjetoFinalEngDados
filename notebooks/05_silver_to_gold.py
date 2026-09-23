from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


# Faixa de destaque do ranking (tempo de permanência no Top N)
TOP_N_HIGHLIGHT = 10

# Janela recente usada no Índice de Tendência
TREND_WINDOW_HOURS = 6

# Idade mínima (em horas) usada nas velocidades, para não inflar
# notícias recém-publicadas
MIN_AGE_HOURS = 1.0

# Pesos do Índice de Tendência (somam 1.0)
TREND_WEIGHTS = {
    "score_velocity": 0.40,
    "comments_velocity": 0.25,
    "rank_momentum": 0.20,
    "current_position": 0.15,
}

NO_DOMAIN_LABEL = "(post sem link)"


def hours_between(end_column, start_column):
    return (
        F.unix_timestamp(end_column) - F.unix_timestamp(start_column)
    ) / 3600


def safe_divide(numerator, denominator):
    return F.when(
        denominator > 0, numerator / denominator
    )


# ---------------------------------------------------------------------------
# gold_story_timeline
# Uma linha por notícia em cada snapshot, com a variação em relação
# ao snapshot anterior da mesma notícia.
# ---------------------------------------------------------------------------

@dp.materialized_view(
    name="gold_story_timeline",
    comment=(
        "Evolução de cada notícia entre snapshots. "
        "Granularidade: uma linha por notícia em cada snapshot "
        "(chave: story_id + collected_at)."
    ),
)
def gold_story_timeline():
    silver = spark.read.table("silver_story_snapshots")

    # Sequência global das coletas, para saber se a notícia estava
    # presente em coletas consecutivas ou se saiu e voltou ao ranking
    collections = (
        silver
        .select("collected_at")
        .distinct()
        .withColumn(
            "collection_seq",
            F.row_number().over(Window.orderBy("collected_at")),
        )
    )

    story_window = (
        Window
        .partitionBy("story_id")
        .orderBy("collected_at")
    )

    timeline = (
        silver
        .join(collections, "collected_at")
        .withColumn("prev_collected_at", F.lag("collected_at").over(story_window))
        .withColumn("prev_collection_seq", F.lag("collection_seq").over(story_window))
        .withColumn("prev_rank", F.lag("rank").over(story_window))
        .withColumn("prev_score", F.lag("score").over(story_window))
        .withColumn("prev_comments", F.lag("comments").over(story_window))
        .withColumn("story_snapshot_seq", F.row_number().over(story_window))
    )

    minutes_since_prev = (
        F.unix_timestamp("collected_at")
        - F.unix_timestamp("prev_collected_at")
    ) / 60

    score_delta = F.col("score") - F.col("prev_score")
    comments_delta = F.col("comments") - F.col("prev_comments")
    age_hours = hours_between("collected_at", "published_at")

    return (
        timeline
        .select(
            "story_id",
            "collected_at",
            "collection_seq",
            "story_snapshot_seq",
            "title",
            "author",
            F.coalesce("domain", F.lit(NO_DOMAIN_LABEL)).alias("domain"),
            "published_at",
            "rank",
            "score",
            "comments",
            F.round(age_hours, 2).alias("age_hours"),
            (F.col("rank") <= TOP_N_HIGHLIGHT).alias("is_top_n"),
            "prev_collected_at",
            "prev_rank",
            F.round(minutes_since_prev, 2).alias("minutes_since_prev"),
            # True quando a notícia também estava na coleta imediatamente anterior
            (
                F.col("collection_seq") - F.col("prev_collection_seq") == 1
            ).alias("is_consecutive"),
            # Positivo = subiu no ranking
            (F.col("prev_rank") - F.col("rank")).alias("rank_change"),
            score_delta.alias("score_delta"),
            comments_delta.alias("comments_delta"),
            F.round(
                safe_divide(score_delta, minutes_since_prev / 60), 2
            ).alias("score_per_hour_interval"),
            F.round(
                safe_divide(comments_delta, minutes_since_prev / 60), 2
            ).alias("comments_per_hour_interval"),
            F.round(
                F.col("score") / F.greatest(age_hours, F.lit(MIN_AGE_HOURS)), 2
            ).alias("score_per_hour_lifetime"),
        )
        .withColumn("gold_loaded_at", F.current_timestamp())
    )


# ---------------------------------------------------------------------------
# gold_story_summary
# Uma linha por notícia: desempenho durante a passagem pelo ranking.
# ---------------------------------------------------------------------------

@dp.materialized_view(
    name="gold_story_summary",
    comment=(
        "Resumo de cada notícia durante sua passagem pelo ranking. "
        "Granularidade: uma linha por notícia (chave: story_id). "
        "Métricas refletem apenas o período em que a notícia esteve no ranking coletado."
    ),
)
def gold_story_summary():
    timeline = spark.read.table("gold_story_timeline")

    latest_window = (
        Window
        .partitionBy("story_id")
        .orderBy(F.col("collected_at").desc())
    )

    first_window = (
        Window
        .partitionBy("story_id")
        .orderBy(F.col("collected_at").asc())
    )

    latest = (
        timeline
        .withColumn("_rn", F.row_number().over(latest_window))
        .filter(F.col("_rn") == 1)
        .select(
            "story_id",
            "title",
            "author",
            "domain",
            "published_at",
            F.col("rank").alias("last_rank"),
            F.col("score").alias("last_score"),
            F.col("comments").alias("last_comments"),
        )
    )

    first = (
        timeline
        .withColumn("_rn", F.row_number().over(first_window))
        .filter(F.col("_rn") == 1)
        .select(
            "story_id",
            F.col("rank").alias("first_rank"),
            F.col("score").alias("first_score"),
            F.col("comments").alias("first_comments"),
        )
    )

    # Tempo no ranking: soma dos intervalos entre coletas consecutivas
    # em que a notícia estava presente
    consecutive_minutes = F.when(
        F.col("is_consecutive"), F.col("minutes_since_prev")
    )
    consecutive_top_n_minutes = F.when(
        F.col("is_consecutive")
        & (F.col("rank") <= TOP_N_HIGHLIGHT)
        & (F.col("prev_rank") <= TOP_N_HIGHLIGHT),
        F.col("minutes_since_prev"),
    )

    aggregates = (
        timeline
        .groupBy("story_id")
        .agg(
            F.min("collected_at").alias("first_seen_at"),
            F.max("collected_at").alias("last_seen_at"),
            F.count("*").alias("snapshots_count"),
            F.sum(F.col("is_top_n").cast("int")).alias("snapshots_in_top_n"),
            F.min("rank").alias("best_rank"),
            F.max("score").alias("peak_score"),
            F.max("comments").alias("peak_comments"),
            F.coalesce(F.sum(consecutive_minutes), F.lit(0)).alias("_minutes_in_ranking"),
            F.coalesce(F.sum(consecutive_top_n_minutes), F.lit(0)).alias("_minutes_in_top_n"),
        )
    )

    latest_collection = timeline.agg(
        F.max("collected_at").alias("latest_collected_at")
    )

    hours_observed = hours_between("last_seen_at", "first_seen_at")
    score_gain = F.col("last_score") - F.col("first_score")
    comments_gain = F.col("last_comments") - F.col("first_comments")

    return (
        latest
        .join(first, "story_id")
        .join(aggregates, "story_id")
        .crossJoin(latest_collection)
        .select(
            "story_id",
            "title",
            "author",
            "domain",
            "published_at",
            "first_seen_at",
            "last_seen_at",
            (F.col("last_seen_at") == F.col("latest_collected_at")).alias("is_in_latest_snapshot"),
            "snapshots_count",
            "snapshots_in_top_n",
            F.round(hours_observed, 2).alias("hours_observed"),
            F.round(F.col("_minutes_in_ranking") / 60, 2).alias("hours_in_ranking"),
            F.round(F.col("_minutes_in_top_n") / 60, 2).alias("hours_in_top_n"),
            "first_rank",
            "best_rank",
            "last_rank",
            "first_score",
            "peak_score",
            "last_score",
            score_gain.alias("score_gain"),
            "first_comments",
            "peak_comments",
            "last_comments",
            comments_gain.alias("comments_gain"),
            F.round(safe_divide(score_gain, hours_observed), 2).alias("score_gain_per_hour"),
            F.round(safe_divide(comments_gain, hours_observed), 2).alias("comments_gain_per_hour"),
        )
        .withColumn("gold_loaded_at", F.current_timestamp())
    )


# ---------------------------------------------------------------------------
# gold_domain_stats
# Uma linha por domínio.
# ---------------------------------------------------------------------------

@dp.materialized_view(
    name="gold_domain_stats",
    comment=(
        "Recorrência e desempenho das fontes (domínios). "
        "Granularidade: uma linha por domínio."
    ),
)
def gold_domain_stats():
    summary = spark.read.table("gold_story_summary")

    return (
        summary
        .groupBy("domain")
        .agg(
            F.countDistinct("story_id").alias("stories_count"),
            F.sum(
                (F.col("best_rank") <= TOP_N_HIGHLIGHT).cast("int")
            ).alias("stories_reached_top_n"),
            F.min("best_rank").alias("best_rank"),
            F.round(F.avg("peak_score"), 1).alias("avg_peak_score"),
            F.max("peak_score").alias("max_peak_score"),
            F.round(F.avg("peak_comments"), 1).alias("avg_peak_comments"),
            F.round(F.avg("hours_in_ranking"), 2).alias("avg_hours_in_ranking"),
            F.min("first_seen_at").alias("first_seen_at"),
            F.max("last_seen_at").alias("last_seen_at"),
        )
        .withColumn("gold_loaded_at", F.current_timestamp())
    )


# ---------------------------------------------------------------------------
# gold_trend_index
# Índice de Tendência das notícias presentes no snapshot mais recente.
# ---------------------------------------------------------------------------

@dp.materialized_view(
    name="gold_trend_index",
    comment=(
        "Índice de Tendência (0 a 100) das notícias presentes no snapshot mais recente. "
        f"Considera as últimas {TREND_WINDOW_HOURS} horas de coleta. "
        "Granularidade: uma linha por notícia do snapshot mais recente."
    ),
)
def gold_trend_index():
    timeline = spark.read.table("gold_story_timeline")

    latest_collected_at = timeline.agg(
        F.max("collected_at").alias("latest_collected_at")
    )

    recent = (
        timeline
        .crossJoin(latest_collected_at)
        .filter(
            F.col("collected_at")
            >= F.col("latest_collected_at")
            - F.expr(f"INTERVAL {TREND_WINDOW_HOURS} HOURS")
        )
    )

    first_in_window = (
        Window
        .partitionBy("story_id")
        .orderBy(F.col("collected_at").asc())
    )

    first_rank_in_window = (
        recent
        .withColumn("_rn", F.row_number().over(first_in_window))
        .filter(F.col("_rn") == 1)
        .select("story_id", F.col("rank").alias("first_rank_in_window"))
    )

    current = (
        recent
        .filter(F.col("collected_at") == F.col("latest_collected_at"))
        .join(first_rank_in_window, "story_id")
    )

    age = F.greatest(F.col("age_hours"), F.lit(MIN_AGE_HOURS))

    components = (
        current
        .withColumn("score_velocity", F.col("score") / age)
        .withColumn("comments_velocity", F.col("comments") / age)
        # Positivo = subiu dentro da janela
        .withColumn("rank_momentum", F.col("first_rank_in_window") - F.col("rank"))
        # Quanto menor o rank, maior o valor
        .withColumn("current_position", -F.col("rank"))
    )

    # Cada componente é normalizado de 0 a 1 pela posição relativa
    # entre as notícias do snapshot atual
    for component in TREND_WEIGHTS:
        components = components.withColumn(
            f"{component}_pct",
            F.percent_rank().over(Window.orderBy(F.col(component))),
        )

    trend_index = sum(
        F.col(f"{component}_pct") * weight
        for component, weight in TREND_WEIGHTS.items()
    ) * 100

    return (
        components
        .withColumn("trend_index", F.round(trend_index, 1))
        .withColumn(
            "trend_rank",
            F.row_number().over(
                Window.orderBy(F.col("trend_index").desc(), F.col("rank").asc())
            ),
        )
        .select(
            "trend_rank",
            "trend_index",
            "story_id",
            "title",
            "domain",
            F.col("collected_at").alias("snapshot_at"),
            "rank",
            "first_rank_in_window",
            "rank_momentum",
            "score",
            "comments",
            "age_hours",
            F.round("score_velocity", 2).alias("score_velocity"),
            F.round("comments_velocity", 2).alias("comments_velocity"),
            F.round("score_velocity_pct", 3).alias("score_velocity_pct"),
            F.round("comments_velocity_pct", 3).alias("comments_velocity_pct"),
            F.round("rank_momentum_pct", 3).alias("rank_momentum_pct"),
            F.round("current_position_pct", 3).alias("current_position_pct"),
        )
        .withColumn("gold_loaded_at", F.current_timestamp())
    )
