import os

import altair as alt
import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

CATALOG_SCHEMA = "hackernews.hacker_news"

# Paleta do painel
PRIMARY = "#FF6600"   # laranja Hacker News
ACCENT = "#2563EB"    # azul para séries secundárias
NEUTRAL = "#94A3B8"   # cinza para elementos de apoio
DARK = "#334155"

st.set_page_config(page_title="Hacker News | Analytics", layout="wide", page_icon="📈")
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


# ---------------------------------------------------------------- helpers
def numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Converte colunas DECIMAL/objeto em números (o Altair não serializa Decimal)."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def short(text, size: int = 60) -> str:
    text = "Sem título" if pd.isna(text) else str(text)
    return text if len(text) <= size else text[: size - 1] + "…"


def as_int(value):
    return None if pd.isna(value) else int(value)


def fmt(value) -> str:
    return "—" if value is None else f"{value:,}".replace(",", ".")


def style(chart, height: int = 380):
    """Acabamento comum a todos os gráficos."""
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True,
            gridDash=[3, 3],
            gridOpacity=0.5,
            domain=False,
            ticks=False,
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight=600,
            labelPadding=6,
            titlePadding=10,
        )
        .configure_axisY(labelLimit=320)
        .configure_legend(orient="top", titleFontSize=12, labelFontSize=12, symbolType="circle")
        .configure_title(fontSize=15, anchor="start", offset=12)
    )


def show(chart, height: int = 380):
    st.altair_chart(style(chart, height), use_container_width=True)


# ---------------------------------------------------------------- dados
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

summary = numeric(summary, ["best_rank", "peak_score", "peak_comments", "score_gain", "hours_in_top_n"])
domains = numeric(domains, ["stories_count", "stories_reached_top_n", "best_rank",
                            "avg_peak_score", "max_peak_score", "avg_hours_in_ranking"])
trends = numeric(trends, ["trend_rank", "trend_index", "rank", "rank_momentum",
                          "score", "comments", "score_velocity"])

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

# ---------------------------------------------------------------- visão geral
with overview:
    a, b, c, d = st.columns(4)
    a.metric("Histórias exibidas", fmt(len(summary)))
    max_score = as_int(summary["peak_score"].max()) if not summary.empty else None
    a_score = fmt(max_score)
    b.metric("Maior pontuação", a_score)
    in_snapshot = int(summary["is_in_latest_snapshot"].fillna(False).astype(bool).sum()) if not summary.empty else 0
    c.metric("No snapshot atual", fmt(in_snapshot))
    avg_hours = summary["hours_in_top_n"].mean() if not summary.empty else None
    d.metric("Média de horas no top", "—" if avg_hours is None or pd.isna(avg_hours) else f"{avg_hours:.1f} h")

    if summary.empty:
        st.info("Nenhuma história disponível para o filtro escolhido.")
    else:
        left, right = st.columns([3, 2], gap="large")

        with left:
            s = summary.dropna(subset=["peak_score", "peak_comments"]).copy()
            s["status"] = s["is_in_latest_snapshot"].fillna(False).astype(bool).map(
                {True: "No snapshot atual", False: "Fora do snapshot"}
            )
            s["title_short"] = s["title"].map(short)
            scatter = (
                alt.Chart(s, title="Pontuação × comentários")
                .mark_circle(opacity=0.7, stroke="white", strokeWidth=0.6)
                .encode(
                    x=alt.X("peak_score:Q", title="Pontuação máxima", scale=alt.Scale(type="symlog")),
                    y=alt.Y("peak_comments:Q", title="Comentários (pico)", scale=alt.Scale(type="symlog")),
                    size=alt.Size("hours_in_top_n:Q", title="Horas no top",
                                  scale=alt.Scale(range=[25, 500]), legend=None),
                    color=alt.Color("status:N", title=None,
                                    scale=alt.Scale(domain=["No snapshot atual", "Fora do snapshot"],
                                                    range=[PRIMARY, NEUTRAL])),
                    tooltip=[
                        alt.Tooltip("title:N", title="História"),
                        alt.Tooltip("domain:N", title="Domínio"),
                        alt.Tooltip("peak_score:Q", title="Pontuação", format=","),
                        alt.Tooltip("peak_comments:Q", title="Comentários", format=","),
                        alt.Tooltip("best_rank:Q", title="Melhor posição"),
                        alt.Tooltip("hours_in_top_n:Q", title="Horas no top", format=".1f"),
                    ],
                )
                .interactive()
            )
            show(scatter, 420)
            st.caption("Escala logarítmica suave; o tamanho do ponto indica as horas no top.")

        with right:
            top = summary.dropna(subset=["peak_score"]).nlargest(10, "peak_score").copy()
            top["label"] = top["title"].map(lambda t: short(t, 42))
            bars = alt.Chart(top, title="Top 10 por pontuação").mark_bar(
                color=PRIMARY, cornerRadiusEnd=4, height=18
            ).encode(
                x=alt.X("peak_score:Q", title=None, axis=alt.Axis(labels=False, grid=False)),
                y=alt.Y("label:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("title:N", title="História"),
                    alt.Tooltip("domain:N", title="Domínio"),
                    alt.Tooltip("peak_score:Q", title="Pontuação", format=","),
                ],
            )
            text = bars.mark_text(align="left", dx=5, fontWeight=600).encode(
                text=alt.Text("peak_score:Q", format=","), color=alt.value(DARK)
            )
            show(alt.layer(bars, text), 420)

    st.subheader("Histórias por pontuação máxima")
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "story_id": st.column_config.TextColumn("ID"),
            "title": st.column_config.TextColumn("Título", width="large"),
            "author": "Autor",
            "domain": "Domínio",
            "published_at": st.column_config.DatetimeColumn("Publicado em", format="DD/MM/YYYY HH:mm"),
            "best_rank": st.column_config.NumberColumn("Melhor posição", format="%d"),
            "peak_score": st.column_config.ProgressColumn(
                "Pontuação máx.", format="%d", min_value=0,
                max_value=int(max_score) if max_score else 1,
            ),
            "peak_comments": st.column_config.NumberColumn("Comentários", format="%d"),
            "score_gain": st.column_config.NumberColumn("Ganho de pontos", format="%d"),
            "hours_in_top_n": st.column_config.NumberColumn("Horas no top", format="%.1f"),
            "is_in_latest_snapshot": st.column_config.CheckboxColumn("No snapshot"),
        },
    )

# ---------------------------------------------------------------- tendências
with trending:
    st.subheader("Tendências no último snapshot")
    if trends.empty:
        st.info("Nenhuma tendência disponível.")
    else:
        st.caption(f"Snapshot: {trends['snapshot_at'].iloc[0]}")
        t = trends.dropna(subset=["trend_index"]).nsmallest(15, "trend_rank").copy()
        t["label"] = t.apply(lambda r: f"{as_int(r['trend_rank']) or '–'}. {short(r['title'], 55)}", axis=1)
        mom = t["rank_momentum"].abs().max()
        mom = 1 if pd.isna(mom) or mom == 0 else float(mom)
        trend_bars = alt.Chart(t, title="Índice de tendência — top 15").mark_bar(
            cornerRadiusEnd=4, height=18
        ).encode(
            x=alt.X("trend_index:Q", title="Índice de tendência"),
            y=alt.Y("label:N", title=None, sort=alt.EncodingSortField("trend_rank", order="ascending")),
            color=alt.Color(
                "rank_momentum:Q",
                title="Momentum de posição",
                scale=alt.Scale(scheme="redyellowgreen", domain=[-mom, mom], domainMid=0),
                legend=alt.Legend(gradientLength=220, direction="horizontal"),
            ),
            tooltip=[
                alt.Tooltip("title:N", title="História"),
                alt.Tooltip("domain:N", title="Domínio"),
                alt.Tooltip("trend_index:Q", title="Índice", format=".2f"),
                alt.Tooltip("rank:Q", title="Posição atual"),
                alt.Tooltip("rank_momentum:Q", title="Momentum", format="+.0f"),
                alt.Tooltip("score_velocity:Q", title="Velocidade (pts)", format=".2f"),
                alt.Tooltip("comments:Q", title="Comentários", format=","),
            ],
        )
        show(trend_bars, max(320, 30 * len(t)))
        st.caption("Verde: a história está subindo no ranking; vermelho: está caindo.")
        st.dataframe(
            trends,
            use_container_width=True,
            hide_index=True,
            column_config={
                "trend_rank": st.column_config.NumberColumn("#", format="%d"),
                "trend_index": st.column_config.NumberColumn("Índice", format="%.2f"),
                "story_id": "ID",
                "title": st.column_config.TextColumn("Título", width="large"),
                "domain": "Domínio",
                "snapshot_at": st.column_config.DatetimeColumn("Snapshot", format="DD/MM/YYYY HH:mm"),
                "rank": st.column_config.NumberColumn("Posição", format="%d"),
                "rank_momentum": st.column_config.NumberColumn("Momentum", format="%+d"),
                "score": st.column_config.NumberColumn("Pontuação", format="%d"),
                "comments": st.column_config.NumberColumn("Comentários", format="%d"),
                "score_velocity": st.column_config.NumberColumn("Velocidade", format="%.2f"),
            },
        )

# ---------------------------------------------------------------- domínios
with domain_tab:
    st.subheader("Domínios por quantidade de histórias")
    if domains.empty:
        st.info("Nenhum domínio disponível.")
    else:
        dd = domains.dropna(subset=["domain", "stories_count"]).nlargest(15, "stories_count").copy()
        dom_tooltip = [
            alt.Tooltip("domain:N", title="Domínio"),
            alt.Tooltip("stories_count:Q", title="Histórias"),
            alt.Tooltip("stories_reached_top_n:Q", title="Chegaram ao top"),
            alt.Tooltip("avg_peak_score:Q", title="Pontuação média", format=",.0f"),
            alt.Tooltip("max_peak_score:Q", title="Pontuação máx.", format=","),
            alt.Tooltip("avg_hours_in_ranking:Q", title="Horas médias no ranking", format=".1f"),
        ]

        left, right = st.columns([3, 2], gap="large")
        with left:
            dom_bars = alt.Chart(dd, title="Top 15 domínios").mark_bar(cornerRadiusEnd=4, height=18).encode(
                x=alt.X("stories_count:Q", title="Histórias", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("domain:N", sort="-x", title=None),
                color=alt.Color("avg_peak_score:Q", title="Pontuação média",
                                scale=alt.Scale(scheme="oranges"),
                                legend=alt.Legend(gradientLength=200, direction="horizontal")),
                tooltip=dom_tooltip,
            )
            dom_text = dom_bars.mark_text(align="left", dx=5, fontWeight=600).encode(
                text="stories_count:Q", color=alt.value(DARK)
            )
            show(alt.layer(dom_bars, dom_text), max(320, 30 * len(dd)))

        with right:
            bubble = (
                alt.Chart(domains.dropna(subset=["domain", "stories_count", "avg_peak_score"]),
                          title="Volume × qualidade")
                .mark_circle(color=ACCENT, opacity=0.6, stroke="white", strokeWidth=0.6)
                .encode(
                    x=alt.X("stories_count:Q", title="Histórias", scale=alt.Scale(type="symlog")),
                    y=alt.Y("avg_peak_score:Q", title="Pontuação média"),
                    size=alt.Size("max_peak_score:Q", scale=alt.Scale(range=[30, 600]), legend=None),
                    tooltip=dom_tooltip,
                )
                .interactive()
            )
            show(bubble, max(320, 30 * len(dd)))

        st.dataframe(
            domains,
            use_container_width=True,
            hide_index=True,
            column_config={
                "domain": "Domínio",
                "stories_count": st.column_config.NumberColumn("Histórias", format="%d"),
                "stories_reached_top_n": st.column_config.NumberColumn("Chegaram ao top", format="%d"),
                "best_rank": st.column_config.NumberColumn("Melhor posição", format="%d"),
                "avg_peak_score": st.column_config.NumberColumn("Pontuação média", format="%.0f"),
                "max_peak_score": st.column_config.NumberColumn("Pontuação máx.", format="%d"),
                "avg_hours_in_ranking": st.column_config.NumberColumn("Horas médias", format="%.1f"),
            },
        )

# ---------------------------------------------------------------- evolução
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
            timeline = numeric(timeline, ["rank", "score", "comments", "rank_change",
                                          "score_delta", "comments_delta"])
            timeline["collected_at"] = pd.to_datetime(timeline["collected_at"])
            timeline["faixa"] = timeline["is_top_n"].fillna(False).astype(bool).map(
                {True: "No top N", False: "Fora do top N"}
            )
            first, last = timeline.iloc[0], timeline.iloc[-1]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Pontuação", fmt(as_int(last["score"])),
                      delta=as_int(last["score"] - first["score"]))
            m2.metric("Comentários", fmt(as_int(last["comments"])),
                      delta=as_int(last["comments"] - first["comments"]))
            m3.metric("Posição atual", fmt(as_int(last["rank"])),
                      delta=as_int(last["rank"] - first["rank"]), delta_color="inverse")
            m4.metric("Melhor posição", fmt(as_int(timeline["rank"].min())))

            x_axis = alt.X("collected_at:T", title=None, axis=alt.Axis(format="%d/%m %H:%M", labelAngle=0))
            tooltip = [
                alt.Tooltip("collected_at:T", title="Coleta", format="%d/%m/%Y %H:%M"),
                alt.Tooltip("rank:Q", title="Posição"),
                alt.Tooltip("score:Q", title="Pontuação", format=","),
                alt.Tooltip("score_delta:Q", title="Δ pontuação", format="+,"),
                alt.Tooltip("comments:Q", title="Comentários", format=","),
                alt.Tooltip("comments_delta:Q", title="Δ comentários", format="+,"),
            ]
            hover = alt.selection_point(fields=["collected_at"], nearest=True, on="mouseover", empty=False)
            base = alt.Chart(timeline).encode(x=x_axis)

            score_line = base.mark_line(color=PRIMARY, strokeWidth=2.5, interpolate="monotone").encode(
                y=alt.Y("score:Q", title="Pontuação", axis=alt.Axis(titleColor=PRIMARY))
            )
            score_area = base.mark_area(color=PRIMARY, opacity=0.08, interpolate="monotone").encode(
                y=alt.Y("score:Q")
            )
            comments_line = base.mark_line(color=ACCENT, strokeWidth=2.5, strokeDash=[6, 3],
                                           interpolate="monotone").encode(
                y=alt.Y("comments:Q", title="Comentários", axis=alt.Axis(titleColor=ACCENT, orient="right"))
            )
            rule = base.mark_rule(color=NEUTRAL, strokeWidth=1).encode(
                opacity=alt.condition(hover, alt.value(0.9), alt.value(0)), tooltip=tooltip
            ).add_params(hover)

            engagement = alt.layer(
                alt.layer(score_area, score_line),
                comments_line,
                rule,
            ).resolve_scale(y="independent").properties(
                title=alt.TitleParams("Pontuação e comentários",
                                      subtitle="Laranja: pontuação (eixo esq.) · Azul tracejado: comentários (eixo dir.)")
            )
            show(engagement, 360)

            rank_line = base.mark_line(color=DARK, strokeWidth=2, interpolate="step-after").encode(
                y=alt.Y("rank:Q", title="Posição", scale=alt.Scale(reverse=True, zero=False, nice=False))
            )
            rank_points = base.mark_circle(size=45, opacity=0.9).encode(
                y="rank:Q",
                color=alt.Color("faixa:N", title=None,
                                scale=alt.Scale(domain=["No top N", "Fora do top N"],
                                                range=[PRIMARY, NEUTRAL])),
                tooltip=tooltip,
            )
            ranking = alt.layer(rank_line, rank_points).properties(
                title=alt.TitleParams("Posição no ranking", subtitle="Quanto mais alto no gráfico, melhor a posição")
            )
            show(ranking, 300)

            st.dataframe(
                timeline.drop(columns=["faixa"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "collected_at": st.column_config.DatetimeColumn("Coleta", format="DD/MM/YYYY HH:mm"),
                    "rank": st.column_config.NumberColumn("Posição", format="%d"),
                    "score": st.column_config.NumberColumn("Pontuação", format="%d"),
                    "comments": st.column_config.NumberColumn("Comentários", format="%d"),
                    "rank_change": st.column_config.NumberColumn("Δ posição", format="%+d"),
                    "score_delta": st.column_config.NumberColumn("Δ pontuação", format="%+d"),
                    "comments_delta": st.column_config.NumberColumn("Δ comentários", format="%+d"),
                    "is_top_n": st.column_config.CheckboxColumn("Top N"),
                },
            )