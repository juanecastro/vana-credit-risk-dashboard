from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .charts import VANA_COLORS, SERIES_COLORS, apply_chart_layout, empty_figure, require_columns

RISK_ORDER = ["E", "D", "C", "B", "A"]


def origination_risk_chart(metrics: pd.DataFrame, metric: str = "dpd_30_rate") -> go.Figure:
    require_columns(metrics, ["risk_band", metric], "origination_risk_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.copy()
    data["risk_band"] = pd.Categorical(data["risk_band"].astype(str), categories=RISK_ORDER, ordered=True)
    data = data.sort_values("risk_band")
    fig = go.Figure(go.Bar(
        x=data["risk_band"].astype(str), y=data[metric],
        marker_color=["#B64B4B", "#D47A4A", "#D9A441", "#6C91D8", VANA_COLORS["navy"]],
        customdata=data[["observed_accounts"]] if "observed_accounts" in data.columns else None,
        hovertemplate="Banda: %{x}<br>Tasa: %{y:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Mora 30+ por banda de riesgo de originación", y_title="Tasa", percent_axis=True, show_legend=False)


def score_channel_heatmap(metrics: pd.DataFrame, metric: str = "dpd_30_rate") -> go.Figure:
    require_columns(metrics, ["canal", "banda_riesgo", metric], "score_channel_heatmap")
    if metrics.empty:
        return empty_figure()
    matrix = metrics.pivot_table(index="canal", columns="banda_riesgo", values=metric, aggfunc="mean")
    matrix = matrix.reindex(columns=[band for band in RISK_ORDER if band in matrix.columns])
    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=matrix.columns.astype(str),
        y=matrix.index.astype(str),
        colorscale=[[0, "#EAF0FF"], [0.5, VANA_COLORS["primary"]], [1, "#9D3030"]],
        colorbar={"title": "Mora 30+", "tickformat": ".0%"},
        hovertemplate="Canal: %{y}<br>Banda: %{x}<br>Mora 30+: %{z:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Mora 30+ por canal y banda de riesgo", x_title="Banda de riesgo", y_title="Canal", height=360)


def partner_risk_chart(metrics: pd.DataFrame, minimum_accounts: int = 30, top_n: int = 15) -> go.Figure:
    require_columns(metrics, ["partner", "observed_accounts", "dpd_30_rate"], "partner_risk_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics[metrics["observed_accounts"] >= minimum_accounts].nlargest(top_n, "dpd_30_rate").sort_values("dpd_30_rate")
    if data.empty:
        return empty_figure("No hay aliados con el mínimo de cuentas seleccionado.")
    fig = go.Figure(go.Bar(
        x=data["dpd_30_rate"], y=data["partner"].astype(str), orientation="h",
        marker_color=VANA_COLORS["red"],
        customdata=data[["observed_accounts", "dpd_30_account_rate"]],
        hovertemplate="Aliado: %{y}<br>Mora por saldo: %{x:.1%}<br>Cuentas: %{customdata[0]}<br>Mora por cuentas: %{customdata[1]:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title=f"Aliados con mayor mora 30+ (mínimo {minimum_accounts} cuentas)", x_title="Mora 30+ sobre saldo", percent_axis=True, height=max(400, 30 * len(data)), show_legend=False)


def behavior_score_chart(metrics: pd.DataFrame) -> go.Figure:
    require_columns(metrics, ["behavior_score_band", "next_month_deterioration_rate"], "behavior_score_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.copy()
    fig = go.Figure(go.Bar(
        x=data["behavior_score_band"].astype(str), y=data["next_month_deterioration_rate"],
        marker_color=VANA_COLORS["primary"],
        customdata=data[["eligible_observations", "unique_accounts"]] if {"eligible_observations", "unique_accounts"}.issubset(data.columns) else None,
        hovertemplate="Score: %{x}<br>Deterioro siguiente mes: %{y:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Deterioro en el siguiente mes por score de comportamiento", y_title="Tasa por observación elegible", percent_axis=True, show_legend=False)


def cutoff_comparison_chart(metrics: pd.DataFrame, metric: str = "dpd_30_rate") -> go.Figure:
    require_columns(metrics, ["policy_period", metric], "cutoff_comparison_chart")
    if metrics.empty:
        return empty_figure()
    fig = go.Figure(go.Bar(
        x=metrics["policy_period"].astype(str), y=metrics[metric],
        marker_color=[VANA_COLORS["slate"], VANA_COLORS["primary"]][:len(metrics)],
        hovertemplate="Periodo: %{x}<br>Tasa: %{y:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Comparación de política a MOB fijo", y_title="Mora 30+ sobre saldo", percent_axis=True, show_legend=False)
