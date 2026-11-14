from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from .charts import VANA_COLORS, SERIES_COLORS, apply_chart_layout, empty_figure, require_columns


def vintage_curve_chart(curve: pd.DataFrame, title: str = "Curvas de mora por cosecha", percent: bool = True) -> go.Figure:
    if curve.empty:
        return empty_figure()
    fig = go.Figure()
    for index, vintage in enumerate(curve.columns):
        fig.add_trace(go.Scatter(
            x=curve.index, y=curve[vintage], mode="lines+markers",
            name=str(vintage), line={"color": SERIES_COLORS[index % len(SERIES_COLORS)], "width": 2},
            marker={"size": 6},
            hovertemplate="MOB: %{x}<br>Cosecha: " + str(vintage) + "<br>Tasa: %{y:.1%}<extra></extra>" if percent else "MOB: %{x}<br>Cosecha: " + str(vintage) + "<br>Valor: %{y:,.0f}<extra></extra>",
        ))
    return apply_chart_layout(fig, title=title, x_title="Meses en libros (MOB)", y_title="Tasa" if percent else None, percent_axis=percent)


def vintage_heatmap(metrics: pd.DataFrame, metric: str = "dpd_30_rate", title: str | None = None) -> go.Figure:
    require_columns(metrics, ["vintage", "mob", metric], "vintage_heatmap")
    if metrics.empty:
        return empty_figure()
    matrix = metrics.pivot_table(index="vintage", columns="mob", values=metric, aggfunc="mean")
    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=[str(value) for value in matrix.columns],
        y=[str(value) for value in matrix.index],
        colorscale=[[0, "#EAF0FF"], [0.5, VANA_COLORS["primary"]], [1, "#9D3030"]],
        colorbar={"title": "Tasa", "tickformat": ".0%"},
        hovertemplate="Cosecha: %{y}<br>MOB: %{x}<br>Tasa: %{z:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title=title or f"Mapa de calor: {metric}", x_title="MOB", y_title="Cosecha", height=max(420, 28 * len(matrix.index)))
