from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .charts import VANA_COLORS, apply_chart_layout, empty_figure, require_columns


def payer_mix_chart(metrics: pd.DataFrame, value: str = "balance_share") -> go.Figure:
    require_columns(metrics, ["tipo_pagador", value], "payer_mix_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.sort_values(value, ascending=False)
    fig = go.Figure(go.Pie(
        labels=data["tipo_pagador"].astype(str), values=data[value], hole=0.58,
        marker={"colors": ["#145192", "#597AF6", "#269A9A", "#D99A24", "#D9534F", "#9BA6B1", "#8064A2"]},
        textinfo="percent",
        hovertemplate="Tipo de pago: %{label}<br>Participación: %{value:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Composición de cartera por comportamiento de pago", show_legend=True)


def payer_transition_heatmap(metrics: pd.DataFrame) -> go.Figure:
    require_columns(metrics, ["tipo_pagador", "next_outcome", "transition_rate"], "payer_transition_heatmap")
    if metrics.empty:
        return empty_figure()
    matrix = metrics.pivot_table(index="tipo_pagador", columns="next_outcome", values="transition_rate", aggfunc="sum", fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=matrix.columns.astype(str), y=matrix.index.astype(str),
        colorscale=[[0, "#F2F5FA"], [0.55, VANA_COLORS["blue_light"]], [1, VANA_COLORS["navy"]]],
        colorbar={"title": "Transición", "tickformat": ".0%"},
        hovertemplate="Pago previo: %{y}<br>Pago siguiente: %{x}<br>Transición: %{z:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Matriz de transición de comportamiento de pago", x_title="Comportamiento siguiente", y_title="Comportamiento previo", height=440)


def delinquency_roll_heatmap(metrics: pd.DataFrame) -> go.Figure:
    require_columns(metrics, ["previous_bucket", "current_bucket", "transition_rate"], "delinquency_roll_heatmap")
    if metrics.empty:
        return empty_figure()
    matrix = metrics.pivot_table(index="previous_bucket", columns="current_bucket", values="transition_rate", aggfunc="sum", fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=matrix.columns.astype(str), y=matrix.index.astype(str),
        colorscale=[[0, "#F2F5FA"], [0.55, VANA_COLORS["blue_light"]], [1, "#B33A3A"]],
        colorbar={"title": "Roll rate", "tickformat": ".0%"},
        hovertemplate="Bucket previo: %{y}<br>Bucket actual: %{x}<br>Transición: %{z:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Matriz de migración de mora", x_title="Bucket actual", y_title="Bucket anterior", height=480)


def collections_outcome_chart(metrics: pd.DataFrame, previous_bucket: str = "MORA_1_29") -> go.Figure:
    require_columns(metrics, ["gestion_cobranza_mes", "previous_mora_bucket", "outcome", "outcome_rate"], "collections_outcome_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics[metrics["previous_mora_bucket"] == previous_bucket]
    if data.empty:
        return empty_figure("No hay observaciones para el bucket de mora seleccionado.")
    fig = go.Figure()
    for outcome, group in data.groupby("outcome"):
        fig.add_trace(go.Bar(
            x=group["gestion_cobranza_mes"].astype(str), y=group["outcome_rate"], name=str(outcome),
            hovertemplate="Gestión: %{x}<br>Resultado: " + str(outcome) + "<br>Tasa: %{y:.1%}<extra></extra>",
        ))
    fig.update_layout(barmode="stack")
    return apply_chart_layout(fig, title=f"Resultado de cobranza · mora previa {previous_bucket}", y_title="Distribución de resultados", percent_axis=True)
