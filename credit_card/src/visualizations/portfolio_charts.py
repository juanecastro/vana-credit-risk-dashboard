from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .charts import VANA_COLORS, SERIES_COLORS, apply_chart_layout, empty_figure, require_columns


def portfolio_trend_chart(metrics: pd.DataFrame, metric: str = "active_balance") -> go.Figure:
    labels = {
        "active_balance": "Saldo de cartera activa",
        "active_accounts": "Tarjetas activas",
        "active_credit_limit": "Límite de crédito activo",
        "new_accounts": "Nuevas tarjetas",
        "cumulative_originations": "Originaciones acumuladas",
        "utilization_rate": "Tasa de utilización",
        "average_balance_per_active_account": "Saldo promedio por tarjeta activa",
    }
    require_columns(metrics, ["fecha_corte", metric], "portfolio_trend_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.sort_values("fecha_corte")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["fecha_corte"], y=data[metric], mode="lines+markers",
        name=labels.get(metric, metric), line={"color": VANA_COLORS["primary"], "width": 3},
        marker={"size": 8},
        customdata=data[["fecha_corte"]].astype(str),
        hovertemplate="Corte: %{x|%d/%m/%Y}<br>Valor: %{y:,.2f}<extra></extra>",
    ))
    return apply_chart_layout(
        fig, title=labels.get(metric, metric),
        y_title="Porcentaje" if metric.endswith("rate") else None,
        percent_axis=metric.endswith("rate"),
        currency_axis=metric in {"active_balance", "active_credit_limit", "average_balance_per_active_account"},
    )


def delinquency_trend_chart(metrics: pd.DataFrame) -> go.Figure:
    columns = ["fecha_corte", "dpd_1_29_balance_rate", "dpd_30_rate"]
    require_columns(metrics, columns, "delinquency_trend_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.sort_values("fecha_corte")
    fig = go.Figure()
    series = [
        ("dpd_1_29_balance_rate", "Mora 1–29 días", VANA_COLORS["amber"]),
        ("dpd_30_rate", "Mora 30+ días", VANA_COLORS["red"]),
    ]
    for column, label, color in series:
        fig.add_trace(go.Scatter(
            x=data["fecha_corte"], y=data[column], mode="lines+markers",
            name=label, line={"color": color, "width": 3}, marker={"size": 7},
            hovertemplate="Corte: %{x|%d/%m/%Y}<br>Tasa: %{y:.1%}<extra></extra>",
        ))
    return apply_chart_layout(fig, title="Evolución de mora sobre saldo activo", y_title="Tasa de saldo", percent_axis=True)


def delinquency_distribution_chart(distribution: pd.DataFrame, value: str = "balance_share") -> go.Figure:
    require_columns(distribution, ["altura_mora", value], "delinquency_distribution_chart")
    if distribution.empty:
        return empty_figure()
    data = distribution.copy()
    fig = go.Figure(go.Bar(
        x=data["altura_mora"].astype(str), y=data[value],
        marker_color=VANA_COLORS["primary"],
        customdata=data[["accounts", "balance"]] if {"accounts", "balance"}.issubset(data.columns) else None,
        hovertemplate="Bucket: %{x}<br>Participación: %{y:.1%}<extra></extra>",
    ))
    return apply_chart_layout(fig, title="Distribución de cartera por altura de mora", y_title="Participación", percent_axis=True, show_legend=False)
