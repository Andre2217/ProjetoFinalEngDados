-- Databricks notebook source

CREATE OR REPLACE VIEW hackernews.hacker_news.pipeline_runs AS

WITH last_status AS (
    SELECT
        origin.pipeline_id,
        origin.pipeline_name,
        origin.update_id,
        FROM_JSON(
            details,
            'STRUCT<update_progress: STRUCT<state: STRING>>'
        ).update_progress.state AS status,
        timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY origin.update_id
            ORDER BY timestamp DESC
        ) AS row_number
    FROM hackernews.hacker_news.pipeline_event_log
    WHERE event_type = 'update_progress'

    QUALIFY row_number = 1
),

durations AS (
    SELECT
        origin.pipeline_id,
        origin.pipeline_name,
        origin.update_id,

        MIN(
            CASE
                WHEN event_type = 'create_update'
                THEN timestamp
            END
        ) AS started_at,

        MAX(
            CASE
                WHEN event_type = 'update_progress'
                 AND FROM_JSON(
                     details,
                     'STRUCT<update_progress: STRUCT<state: STRING>>'
                 ).update_progress.state
                     IN ('COMPLETED', 'FAILED', 'CANCELED')
                THEN timestamp
            END
        ) AS finished_at

    FROM hackernews.hacker_news.pipeline_event_log

    WHERE origin.update_id IS NOT NULL

    GROUP BY
        origin.pipeline_id,
        origin.pipeline_name,
        origin.update_id
),

flow_progress AS (
    SELECT
        origin.pipeline_id,
        origin.pipeline_name,
        origin.update_id,
        origin.flow_name,

        TRY_CAST(
            details:flow_progress.metrics.num_output_rows
            AS BIGINT
        ) AS output_rows

    FROM hackernews.hacker_news.pipeline_event_log

    WHERE event_type = 'flow_progress'
      AND origin.flow_name IN (
          'bronze_stories',
          'quarantine_stories'
      )
),

flow_totals AS (
    SELECT
        pipeline_id,
        pipeline_name,
        update_id,

        SUM(
            CASE
                WHEN flow_name = 'bronze_stories'
                THEN COALESCE(output_rows, 0)
                ELSE 0
            END
        ) AS bronze_records,

        SUM(
            CASE
                WHEN flow_name = 'quarantine_stories'
                THEN COALESCE(output_rows, 0)
                ELSE 0
            END
        ) AS quarantined_records

    FROM flow_progress

    GROUP BY
        pipeline_id,
        pipeline_name,
        update_id
)

SELECT
    status.pipeline_id,
    status.pipeline_name,
    status.update_id,

    duration.started_at,
    duration.finished_at,

    status.status,

    COALESCE(flows.bronze_records, 0)
        AS bronze_records,

    COALESCE(flows.quarantined_records, 0)
        AS quarantined_records,

    COALESCE(flows.bronze_records, 0)
        + COALESCE(flows.quarantined_records, 0)
        AS processed_records,

    ROUND(
        COALESCE(flows.bronze_records, 0)
        /
        NULLIF(
            COALESCE(flows.bronze_records, 0)
            + COALESCE(flows.quarantined_records, 0),
            0
        )
        * 100,
        2
    ) AS valid_percent

FROM last_status status

LEFT JOIN durations duration
    ON status.pipeline_id = duration.pipeline_id
   AND status.update_id = duration.update_id

LEFT JOIN flow_totals flows
    ON status.pipeline_id = flows.pipeline_id
   AND status.update_id = flows.update_id;


CREATE OR REPLACE VIEW
hackernews.hacker_news.quality_expectations AS

WITH expectation_events AS (
    SELECT
        origin.pipeline_id,
        origin.pipeline_name,
        origin.update_id,
        timestamp,

        EXPLODE(
            FROM_JSON(
                details:flow_progress:data_quality:expectations,
                'ARRAY<
                    STRUCT<
                        name: STRING,
                        dataset: STRING,
                        passed_records: BIGINT,
                        failed_records: BIGINT
                    >
                >'
            )
        ) AS expectation

    FROM hackernews.hacker_news.pipeline_event_log

    WHERE event_type = 'flow_progress'
      AND details:flow_progress:data_quality:expectations
          IS NOT NULL
)

SELECT
    pipeline_id,
    pipeline_name,
    update_id,

    MAX(timestamp) AS processed_at,

    expectation.dataset AS dataset,
    expectation.name AS expectation,

    SUM(expectation.passed_records)
        AS passed_records,

    SUM(expectation.failed_records)
        AS failed_records,

    ROUND(
        SUM(expectation.passed_records)
        /
        NULLIF(
            SUM(expectation.passed_records)
            + SUM(expectation.failed_records),
            0
        )
        * 100,
        2
    ) AS success_percent

FROM expectation_events

GROUP BY
    pipeline_id,
    pipeline_name,
    update_id,
    expectation.dataset,
    expectation.name;


SELECT *
FROM hackernews.hacker_news.pipeline_runs
ORDER BY started_at DESC;


SELECT *
FROM hackernews.hacker_news.quality_expectations
ORDER BY processed_at DESC, expectation;