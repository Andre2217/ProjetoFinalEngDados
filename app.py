import os

import altair as alt
import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

SCHEMA = "hackernews.hacker_news"
BLUE = "#4f7cff"
ORANGE = "#ffad66"

st.set_page_config(page_title="Hacker News | Radar", page_icon="📡", layout="wide")
st.markdown("""
<style>
:root {color-scheme: dark;}
.block-container {max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem;}
[data-testid="stAppViewContainer"] {background: #0c1220; color: #e7edf8;}
[data-testid="stSidebar"] {background: #121b2c; border-right: 1px solid #26354e;}
.hero {padding: 28px 34px; border: 1px solid #304263; border-radius: 20px;
  background: linear-gradient(115deg,#182a4a 0%,#101b30 62%,#172b3e 100%); margin-bottom: 20px;}
.eyebrow {letter-spacing: .18em; text-transform: uppercase; color: #8db6ff; font-size: .78rem; font-weight: 700;}
.hero h1 {font-size: 2.25rem; line-height: 1.15; margin: .35rem 0 .5rem; color: #f7faff;}
.hero p {color: #b9c9e1; margin: 0;}
.section {font-size: 1.32rem; font-weight: 700; color: #f2f6ff; margin: 1.1rem 0 .15rem;}
.hint {color: #a9bad3; font-size: .88rem; margin-bottom: 1rem;}
[data-testid="stMetric"] {background: #162238; border: 1px solid #2a3b56; padding: 16px 19px; border-radius: 15px;}
[data-testid="stMetricLabel"] {color: #aebed5;}
[data-testid="stMetricValue"] {color: #f5f8ff;}
.stTabs [data-baseweb="tab-list"] {gap: 8px;}
.stTabs [data-baseweb="tab"] {background: #152139; border-radius: 10px 10px 0 0; padding: 10px 20px;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">Data intelligence · Hacker News</div><h1>Radar de histórias</h1><p>Descubra o que ganhou tração, quais domínios se destacam e como cada história evoluiu.</p></div>', unsafe_allow_html=True)

warehouse_path = os.getenv("DATABRICKS_HTTP_PATH", "")
with st.sidebar:
    st.header("Filtros e conexão")
    if not warehouse_path:
        warehouse_path = st.text_input("HTTP Path do SQL Warehouse", placeholder="/sql/1.0/warehouses/…")
    if st.button("↻ Atualizar consultas", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("As consultas ficam em cache por 5 minutos. Dados de tendência representam o último snapshot disponível.")

if not warehouse_path:
    st.info("Informe o HTTP Path do SQL Warehouse na barra lateral para carregar o painel.")
    st.stop()
if not warehouse_path.startswith("/sql/1.0/warehouses/"):
    st.error("O HTTP Path deve começar com /sql/1.0/warehouses/.")
    st.stop()

@st.cache_data(ttl=300, show_spinner="Carregando indicadores…")
def query(statement: str, http_path: str) -> pd.DataFrame:
    cfg = Config()
    host = cfg.host.removeprefix("https://").removeprefix("http://").rstrip("/")
    with sql.connect(server_hostname=host, http_path=http_path,
                     credentials_provider=lambda: cfg.authenticate,
                     _use_arrow_native_complex_types=False) as conn:
        with conn.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall_arrow().to_pandas()

def number(value):
    return f"{int(value):,}".replace(",", ".") if pd.notna(value) else "—"

def chart(data, x, y, color=BLUE, height=340, reverse=False):
    return (alt.Chart(data).mark_bar(color=color, cornerRadiusEnd=5)
            .encode(x=alt.X(x, title=None, axis=alt.Axis(grid=True, gridColor="#29364c")),
                    y=alt.Y(y, title=None, sort="-x" if not reverse else "x",
                            axis=alt.Axis(labelLimit=260)),
                    tooltip=list(data.columns))
            .properties(height=height).configure_view(stroke=None)
            .configure_axis(labelColor="#b9c8dc", titleColor="#b9c8dc"))

try:
    totals = query(f"""SELECT count(*) AS stories,
        sum(CASE WHEN is_in_latest_snapshot THEN 1 ELSE 0 END) AS active,
        max(peak_score) AS highest_score
        FROM {SCHEMA}.gold_story_summary""", warehouse_path)
    summary = query(f"""SELECT story_id,title,author,domain,published_at,best_rank,
        peak_score,peak_comments,score_gain,hours_in_top_n,is_in_latest_snapshot
        FROM {SCHEMA}.gold_story_summary
        ORDER BY peak_score DESC NULLS LAST LIMIT 500""", warehouse_path)
    domains = query(f"""SELECT domain,stories_count,stories_reached_top_n,best_rank,
        avg_peak_score,max_peak_score,avg_hours_in_ranking
        FROM {SCHEMA}.gold_domain_stats ORDER BY stories_count DESC NULLS LAST LIMIT 100""", warehouse_path)
    trends = query(f"""SELECT trend_rank,trend_index,story_id,title,domain,snapshot_at,
        rank,rank_momentum,score,comments,score_velocity
        FROM {SCHEMA}.gold_trend_index
        WHERE snapshot_at=(SELECT max(snapshot_at) FROM {SCHEMA}.gold_trend_index)
        ORDER BY trend_rank ASC NULLS LAST LIMIT 100""", warehouse_path)
except Exception as exc:
    st.error(f"Não foi possível consultar as tabelas Gold: {exc}")
    st.stop()

with st.sidebar:
    choices = sorted(set(summary["domain"].dropna().astype(str)) |
                     set(domains["domain"].dropna().astype(str)) |
                     set(trends["domain"].dropna().astype(str)))
    domain_filter = st.selectbox("Domínio", ["Todos"] + choices)
    min_score = st.number_input("Pontuação mínima (histórias)", min_value=0, value=0, step=50)

if domain_filter != "Todos":
    summary = summary[summary["domain"] == domain_filter]
    domains = domains[domains["domain"] == domain_filter]
    trends = trends[trends["domain"] == domain_filter]
summary = summary[summary["peak_score"].fillna(0) >= min_score]

snapshot = pd.to_datetime(trends["snapshot_at"].iloc[0]).strftime("%d/%m/%Y %H:%M") if not trends.empty else "indisponível"
st.caption(f"Último snapshot de tendências: {snapshot} · Filtro de domínio: {domain_filter}")

if domain_filter == "Todos" and min_score == 0 and not totals.empty:
    kpi_stories = number(totals["stories"].iloc[0])
    kpi_active = number(totals["active"].iloc[0])
    kpi_score = number(totals["highest_score"].iloc[0])
    scope = "Total nas tabelas Gold"
else:
    kpi_stories = number(len(summary))
    kpi_active = number(summary["is_in_latest_snapshot"].fillna(False).sum()) if not summary.empty else "0"
    kpi_score = number(summary["peak_score"].max()) if not summary.empty else "—"
    scope = "Amostra filtrada (até 500 histórias por pontuação)"

st.caption(scope)
a, b, c = st.columns(3)
a.metric("Histórias", kpi_stories)
b.metric("Presentes no último snapshot", kpi_active)
c.metric("Maior pontuação", kpi_score)
st.write("")

one, two, three, four = st.tabs(["Panorama", "Em alta", "Domínios", "Trajetória"])
with one:
    st.markdown('<div class="section">Histórias em destaque</div><div class="hint">Seleção das 500 histórias com maior pontuação máxima. O filtro atua sobre essa seleção.</div>', unsafe_allow_html=True)
    if summary.empty:
        st.info("Nenhuma história atende aos filtros selecionados.")
    else:
        top = summary.nlargest(12, "peak_score").copy()
        top["História"] = top["title"].fillna("Sem título").str.slice(0, 57)
        top["Pico de pontos"] = top["peak_score"]
        st.altair_chart(chart(top[["História", "Pico de pontos"]], "Pico de pontos:Q", "História:N", height=410), use_container_width=True)
        with st.expander("Explorar histórias", expanded=True):
            st.dataframe(summary.rename(columns={"title":"Título","domain":"Domínio","author":"Autor",
                "published_at":"Publicação","peak_score":"Pico de pontos","peak_comments":"Pico de comentários",
                "best_rank":"Melhor posição","score_gain":"Ganho de pontos","hours_in_top_n":"Horas no Top N"})
                [["Título","Domínio","Autor","Publicação","Pico de pontos","Pico de comentários","Melhor posição","Ganho de pontos","Horas no Top N"]],
                hide_index=True, use_container_width=True, height=410)
with two:
    st.markdown('<div class="section">Em alta agora</div><div class="hint">Ranking do snapshot mais recente, ordenado pelo índice de tendência calculado na camada Gold.</div>', unsafe_allow_html=True)
    if trends.empty:
        st.info("Nenhuma tendência disponível para este domínio.")
    else:
        top = trends.head(12).copy()
        top["História"] = top["title"].fillna("Sem título").str.slice(0, 57)
        top["Índice de tendência"] = top["trend_index"]
        st.altair_chart(chart(top[["História","Índice de tendência"]], "Índice de tendência:Q", "História:N", ORANGE, 410), use_container_width=True)
        st.dataframe(trends.rename(columns={"trend_rank":"Posição tendência", "title":"Título", "domain":"Domínio",
            "trend_index":"Índice", "rank":"Posição HN", "rank_momentum":"Movimento", "score":"Pontos",
            "comments":"Comentários", "score_velocity":"Pontos/hora"})
            [["Posição tendência","Título","Domínio","Índice","Posição HN","Movimento","Pontos","Comentários","Pontos/hora"]],
            hide_index=True, use_container_width=True, height=400)
with three:
    st.markdown('<div class="section">Fontes que mais aparecem</div><div class="hint">Volume de histórias por domínio, com desempenho médio e presença no Top N.</div>', unsafe_allow_html=True)
    if domains.empty:
        st.info("Nenhum domínio disponível para este filtro.")
    else:
        top = domains.dropna(subset=["domain"]).head(15).copy()
        top["Domínio"] = top["domain"]
        top["Histórias"] = top["stories_count"]
        st.altair_chart(chart(top[["Domínio","Histórias"]], "Histórias:Q", "Domínio:N", height=460), use_container_width=True)
        st.dataframe(domains.rename(columns={"domain":"Domínio","stories_count":"Histórias",
            "stories_reached_top_n":"Chegaram ao Top N","best_rank":"Melhor posição",
            "avg_peak_score":"Média do pico de pontos","max_peak_score":"Maior pontuação",
            "avg_hours_in_ranking":"Média de horas no ranking"}),
            hide_index=True, use_container_width=True, height=360)
with four:
    st.markdown('<div class="section">Trajetória da história</div><div class="hint">Acompanhe pontuação, comentários e posição em cada coleta.</div>', unsafe_allow_html=True)
    if summary.empty:
        st.info("Nenhuma história disponível para os filtros atuais.")
    else:
        titles = summary.drop_duplicates("story_id").set_index("story_id")["title"].fillna("Sem título").to_dict()
        story_id = st.selectbox("Escolha uma história", list(titles), format_func=lambda sid: f"{titles[sid]} · {sid}")
        escaped_id = str(story_id).replace("'", "''")
        try:
            timeline = query(f"""SELECT collected_at,rank,score,comments,rank_change,
                score_delta,comments_delta,is_top_n FROM {SCHEMA}.gold_story_timeline
                WHERE story_id='{escaped_id}' ORDER BY collected_at DESC LIMIT 1000""", warehouse_path)
        except Exception as exc:
            st.error(f"Falha ao consultar a trajetória: {exc}")
            st.stop()
        if timeline.empty:
            st.info("Não há coletas dessa história.")
        else:
            timeline["collected_at"] = pd.to_datetime(timeline["collected_at"])
            timeline = timeline.sort_values("collected_at")
            x, y, z = st.columns(3)
            x.metric("Coletas exibidas", number(len(timeline)))
            y.metric("Pico de pontos", number(timeline["score"].max()))
            z.metric("Melhor posição", number(timeline["rank"].min()))
            long = timeline.melt(id_vars="collected_at", value_vars=["score","comments"], var_name="Métrica", value_name="Valor")
            line = alt.Chart(long).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X("collected_at:T", title="Coleta"), y=alt.Y("Valor:Q", title="Valor"),
                color=alt.Color("Métrica:N", scale=alt.Scale(domain=["score","comments"], range=[BLUE,ORANGE])),
                tooltip=["collected_at:T","Métrica:N","Valor:Q"]).properties(height=350)
            st.altair_chart(line, use_container_width=True)
            st.caption("Posição no ranking: números menores representam posições melhores.")
            ranks = alt.Chart(timeline).mark_line(point=True, color="#8fe0c2", strokeWidth=3).encode(
                x=alt.X("collected_at:T", title="Coleta"),
                y=alt.Y("rank:Q", title="Posição", scale=alt.Scale(reverse=True)),
                tooltip=["collected_at:T","rank:Q"]).properties(height=260)
            st.altair_chart(ranks, use_container_width=True)
            with st.expander("Ver coletas detalhadas"):
                st.dataframe(timeline.rename(columns={"collected_at":"Coleta","rank":"Posição",
                    "score":"Pontos","comments":"Comentários","rank_change":"Mudança na posição",
                    "score_delta":"Variação de pontos","comments_delta":"Variação de comentários","is_top_n":"No Top N"}),
                    hide_index=True, use_container_width=True)
