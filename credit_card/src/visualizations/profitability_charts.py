from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .charts import VANA_COLORS, apply_chart_layout, empty_figure, require_columns


def revenue_proxy_chart(metrics: pd.DataFrame) -> go.Figure:
    require_columns(metrics, ["fecha_corte", "interest_revenue_proxy", "late_fee_revenue_proxy"], "revenue_proxy_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.sort_values("fecha_corte")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=data["fecha_corte"], y=data["interest_revenue_proxy"], name="Intereses (proxy)", marker_color=VANA_COLORS["primary"]))
    fig.add_trace(go.Bar(x=data["fecha_corte"], y=data["late_fee_revenue_proxy"], name="Cargos por mora", marker_color=VANA_COLORS["amber"]))
    fig.update_layout(barmode="stack")
    return apply_chart_layout(fig, title="Ingresos observados: intereses y cargos por mora", y_title="Quetzales", currency_axis=True)


def chargeoff_trend_chart(metrics: pd.DataFrame) -> go.Figure:
    require_columns(metrics, ["fecha_corte", "chargeoff_balance", "cumulative_chargeoff_balance"], "chargeoff_trend_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.sort_values("fecha_corte")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=data["fecha_corte"], y=data["chargeoff_balance"], name="Castigos del mes", marker_color=VANA_COLORS["red"]))
    fig.add_trace(go.Scatter(x=data["fecha_corte"], y=data["cumulative_chargeoff_balance"], name="Castigos acumulados", mode="lines+markers", yaxis="y2", line={"color": VANA_COLORS["navy"], "width": 3}))
    fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "title": "Acumulado (Q)", "showgrid": False, "tickprefix": "Q ", "tickformat": ",.0f"})
    return apply_chart_layout(fig, title="Evolución de castigos", y_title="Castigos del mes (Q)", currency_axis=True)
