import duckdb
import pandas as pd
import streamlit as st

from src.config import DEFAULT_STORY_LIMIT, DUCKDB_PATH
from src.orchestration.pipeline_flow import run_pipeline


st.set_page_config(
    page_title="Hacker News Trends",
    page_icon="💻",
    layout="wide",
)

st.title("💻 Hacker News — Pipeline Bronze e Silver")
st.caption(
    "Etapa atual do projeto: ingestão real, Bronze histórico, validação e Silver em DuckDB."
)

with st.sidebar:
    st.header("Pipeline")
    story_limit = st.slider(
        "Quantidade de histórias",
        min_value=10,
        max_value=100,
        value=DEFAULT_STORY_LIMIT,
        step=10,
    )

    if st.button("🔄 Executar nova ingestão", use_container_width=True):
        try:
            with st.spinner("Consultando Hacker News e atualizando Bronze/Silver..."):
                result = run_pipeline(limit=story_limit)

            st.success(
                f"Snapshot concluído: {result['records_valid']} registros válidos."
            )

            if result["records_rejected"]:
                st.warning(
                    f"{result['records_rejected']} registro(s) foram enviados para quarentena."
                )
        except Exception as error:
            st.error(f"Falha na pipeline: {error}")

if not DUCKDB_PATH.exists():
    st.info(
        "Ainda não existem dados na Silver. Execute uma ingestão pela barra lateral."
    )
    st.stop()

with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
    table_exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'silver'
          AND table_name = 'story_snapshots'
        """
    ).fetchone()[0]

    if not table_exists:
        st.info(
            "O banco existe, mas a tabela Silver ainda não foi criada. Execute uma ingestão."
        )
        st.stop()

    latest_snapshot = connection.execute(
        """
        SELECT *
        FROM silver.story_snapshots
        WHERE collected_at = (
            SELECT MAX(collected_at)
            FROM silver.story_snapshots
        )
        ORDER BY rank
        """
    ).df()

    total_snapshots = connection.execute(
        "SELECT COUNT(DISTINCT snapshot_id) FROM silver.story_snapshots"
    ).fetchone()[0]

if latest_snapshot.empty:
    st.info("A tabela Silver está vazia.")
    st.stop()

latest_snapshot["published_at"] = pd.to_datetime(
    latest_snapshot["published_at"], errors="coerce"
)
latest_snapshot["collected_at"] = pd.to_datetime(
    latest_snapshot["collected_at"], errors="coerce"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Histórias no snapshot", len(latest_snapshot))
col2.metric("Snapshots armazenados", total_snapshots)
col3.metric("Score acumulado", int(latest_snapshot["score"].sum()))
col4.metric("Comentários", int(latest_snapshot["comments_count"].sum()))

st.caption(f"Última coleta: {latest_snapshot['collected_at'].max()} UTC")

st.subheader("Silver — último snapshot")
st.dataframe(
    latest_snapshot[
        [
            "rank",
            "story_id",
            "title",
            "score",
            "comments_count",
            "domain",
            "published_at",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.info(
    "Esta tela é apenas para inspeção da etapa atual. A camada Gold e o dashboard analítico final serão implementados depois."
)
