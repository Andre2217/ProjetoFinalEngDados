import os

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

CATALOG_SCHEMA = "hackernews.hacker_news"

st.set_page_config(page_title="Hacker News | Analytics", layout="wide")
st.title("Hacker News | Analytics")
st.caption("Indicadores calculados a partir das tabelas Gold do Databricks")

warehouse_path = os.getenv("DATABRICKS_HTTP_PATH", "")
if not warehouse_path:
    warehouse_path = st.sidebar.text_input(
        "HTTP Path do SQL Warehouse", placeholder="/sql/1.0/warehouses/…"
    )
if not warehouse_path:
    st.info("Informe o HTTP Path do SQL Warehouse na barra lateral para carregar o painel.")
    st.stop()
if not warehouse_path.startswith("/sql/1.0/warehouses/"):
    st.error("O HTTP Path deve começar com /sql/1.0/warehouses/.")
    st.stop()

cfg = Config()

@st.cache_data(ttl=300, show_spinner="Consultando o Databricks…")
def query(statement: str, http_path: str) -> pd.DataFrame:
    host = cfg.host.removeprefix("https://").removeprefix("http://").rstrip("/")
    with sql.connect(
        server_hostname=host,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall_arrow().to_pandas()

try:
    summary = query(f"""
        SELECT story_id, title, author, domain, published_at, best_rank,
               peak_score, peak_comments, score_gain, hours_in_top_n,
               is_in_latest_snapshot
        FROM {CATALOG_SCHEMA}.gold_story_summary
        ORDER BY peak_score DESC NULLS LAST LIMIT 500
    """, warehouse_path)
    domains = query(f"""
        SELECT domain, stories_count, stories_reached_top_n, best_rank,
               avg_peak_score, max_peak_score, avg_hours_in_ranking
        FROM {CATALOG_SCHEMA}.gold_domain_stats
        ORDER BY stories_count DESC NULLS LAST LIMIT 100
    """, warehouse_path)
    trends = query(f"""
        SELECT trend_rank, trend_index, story_id, title, domain, snapshot_at,
               rank, rank_momentum, score, comments, score_velocity
        FROM {CATALOG_SCHEMA}.gold_trend_index
        WHERE snapshot_at = (SELECT MAX(snapshot_at) FROM {CATALOG_SCHEMA}.gold_trend_index)
        ORDER BY trend_rank ASC NULLS LAST LIMIT 100
    """, warehouse_path)
except Exception as exc:
    st.error(f"Falha ao consultar as tabelas Gold: {exc}")
    st.stop()

if not summary.empty:
    domains_available = sorted(summary["domain"].dropna().astype(str).unique().tolist())
    selected_domain = st.sidebar.selectbox("Domínio", ["Todos"] + domains_available)
    if selected_domain != "Todos":
        summary = summary[summary["domain"] == selected_domain]
        domains = domains[domains["domain"] == selected_domain]
        trends = trends[trends["domain"] == selected_domain]

if st.sidebar.button("Atualizar dados"):
    query.clear()
    st.rerun()

overview, trending, domain_tab, evolution = st.tabs(
    ["Visão geral", "Tendências", "Domínios", "Evolução da história"]
)
with overview:
    a, b, c = st.columns(3)
    a.metric("Histórias exibidas", f"{len(summary):,}")
    b.metric("Maior pontuação", int(summary["peak_score"].max()) if not summary.empty and summary["peak_score"].notna().any() else 0)
    c.metric("Histórias no snapshot atual", int(summary["is_in_latest_snapshot"].fillna(False).sum()) if not summary.empty else 0)
    st.subheader("Histórias por pontuação máxima")
    st.dataframe(summary, use_container_width=True, hide_index=True)
with trending:
    st.subheader("Tendências no último snapshot")
    if trends.empty:
        st.info("Nenhuma tendência disponível.")
    else:
        st.caption(f"Snapshot: {trends['snapshot_at'].iloc[0]}")
        st.dataframe(trends, use_container_width=True, hide_index=True)
with domain_tab:
    st.subheader("Domínios por quantidade de histórias")
    if domains.empty:
        st.info("Nenhum domínio disponível.")
    else:
        chart = domains.dropna(subset=["domain"]).head(20).set_index("domain")
        st.bar_chart(chart["stories_count"])
        st.dataframe(domains, use_container_width=True, hide_index=True)
with evolution:
    st.subheader("Evolução de uma história")
    if summary.empty:
        st.info("Nenhuma história disponível para o filtro escolhido.")
    else:
        options = summary.drop_duplicates("story_id").set_index("story_id")["title"].fillna("Sem título").to_dict()
        story_id = st.selectbox("História", list(options), format_func=lambda sid: f"{options[sid]} ({sid})")
        # story_id vem somente das linhas retornadas pela consulta; aspas são duplicadas para SQL.
        escaped_id = str(story_id).replace("'", "''")
        try:
            timeline = query(f"""
                SELECT collected_at, rank, score, comments, rank_change,
                       score_delta, comments_delta, is_top_n
                FROM {CATALOG_SCHEMA}.gold_story_timeline
                WHERE story_id = '{escaped_id}'
                ORDER BY collected_at ASC LIMIT 1000
            """, warehouse_path)
        except Exception as exc:
            st.error(f"Falha ao consultar a evolução: {exc}")
            st.stop()
        if timeline.empty:
            st.info("Sem coletas para essa história.")
        else:
            timeline["collected_at"] = pd.to_datetime(timeline["collected_at"])
            timeline = timeline.set_index("collected_at")
            st.write("Pontuação e comentários")
            st.line_chart(timeline[["score", "comments"]])
            st.write("Posição no ranking (menor número é melhor)")
            st.line_chart(timeline[["rank"]])
            st.dataframe(timeline, use_container_width=True)
