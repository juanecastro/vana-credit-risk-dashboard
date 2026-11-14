from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .charts import VANA_COLORS, apply_chart_layout, empty_figure, require_columns


def campaign_followup_chart(metrics: pd.DataFrame, metric: str = "cumulative_ever_30_or_chargeoff_rate_itt") -> go.Figure:
    require_columns(metrics, ["campaign_date", "horizon_months", "group", metric], "campaign_followup_chart")
    if metrics.empty:
        return empty_figure()
    fig = go.Figure()
    colors = {"TRATAMIENTO": VANA_COLORS["primary"], "CONTROL": VANA_COLORS["slate"]}
    for (campaign_date, group_name), group in metrics.groupby(["campaign_date", "group"]):
        group = group.sort_values("horizon_months")
        fig.add_trace(go.Scatter(
            x=group["horizon_months"], y=group[metric], mode="lines+markers",
            name=f"{pd.Timestamp(campaign_date):%b %Y} · {group_name}",
            line={"color": colors.get(str(group_name), VANA_COLORS["navy"]), "width": 2, "dash": "solid" if group_name == "TRATAMIENTO" else "dash"},
            customdata=group[["assigned_accounts"]] if "assigned_accounts" in group.columns else None,
            hovertemplate="Horizonte: %{x} meses<br>Tasa acumulada: %{y:.1%}<extra></extra>",
        ))
    return apply_chart_layout(fig, title="Deterioro acumulado por intención de tratar", x_title="Meses desde campaña", y_title="Tasa acumulada", percent_axis=True)


def campaign_segment_chart(metrics: pd.DataFrame, metric: str = "cumulative_ever_30_or_chargeoff_rate_itt") -> go.Figure:
    require_columns(metrics, ["segment", "group", metric], "campaign_segment_chart")
    if metrics.empty:
        return empty_figure()
    data = metrics.copy()
    fig = go.Figure()
    colors = {"TRATAMIENTO": VANA_COLORS["primary"], "CONTROL": VANA_COLORS["slate"]}
    for group_name, group in data.groupby("group"):
        fig.add_trace(go.Bar(
            x=group["segment"].astype(str), y=group[metric], name=str(group_name),
            marker_color=colors.get(str(group_name), VANA_COLORS["navy"]),
            hovertemplate="Segmento: %{x}<br>Tasa: %{y:.1%}<extra></extra>",
        ))
    fig.update_layout(barmode="group")
    return apply_chart_layout(fig, title="Resultado de campaña por segmento", y_title="Tasa acumulada ITT", percent_axis=True)
