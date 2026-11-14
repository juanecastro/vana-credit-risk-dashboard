from __future__ import annotations

from typing import Iterable
import pandas as pd
import plotly.graph_objects as go


VANA_COLORS = {
    "primary": "#597AF6",
    "navy": "#145192",
    "slate": "#9BA6B1",
    "blue_light": "#AFC0FF",
    "blue_dark": "#2445B8",
    "green": "#23966B",
    "amber": "#D99A24",
    "red": "#D9534F",
    "purple": "#8064A2",
    "teal": "#269A9A",
    "gray": "#78838F",
    "light_gray": "#E7EBF0",
}

SERIES_COLORS = [
    VANA_COLORS["primary"], VANA_COLORS["navy"], VANA_COLORS["green"],
    VANA_COLORS["amber"], VANA_COLORS["purple"], VANA_COLORS["teal"],
    VANA_COLORS["red"], VANA_COLORS["slate"],
]


def apply_chart_layout(
    fig: go.Figure,
    *,
    title: str | None = None,
    height: int = 420,
    y_title: str | None = None,
    x_title: str | None = None,
    percent_axis: bool = False,
    currency_axis: bool = False,
    show_legend: bool = True,
) -> go.Figure:
    yaxis = {"title": y_title, "gridcolor": "#E9EDF2", "zerolinecolor": "#D7DDE5"}
    if percent_axis:
        yaxis["tickformat"] = ".0%"
    if currency_axis:
        yaxis["tickprefix"] = "Q "
        yaxis["tickformat"] = ",.0f"

    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"} if title else None,
        template="plotly_white",
        height=height,
        margin={"l": 16, "r": 16, "t": 64 if title else 28, "b": 20},
        font={"family": "Arial, sans-serif", "size": 12, "color": "#263445"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hoverlabel={"bgcolor": "white", "font_size": 12},
        hovermode="closest",
        clickmode="event+select",
        dragmode="select",
        colorway=SERIES_COLORS,
    )
    fig.update_xaxes(title=x_title, showgrid=False, linecolor="#D7DDE5")
    fig.update_yaxes(**yaxis)
    if not show_legend:
        fig.update_layout(showlegend=False)
    return fig


def empty_figure(message: str = "No hay datos para los filtros seleccionados.", height: int = 360) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 14, "color": VANA_COLORS["gray"]},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(template="plotly_white", height=height, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    return fig


def require_columns(data: pd.DataFrame, columns: Iterable[str], chart_name: str) -> bool:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"{chart_name}: faltan columnas requeridas: {missing}")
    return not data.empty


def render_plotly_chart(
    fig: go.Figure,
    *,
    key: str,
    use_container_width: bool = True,
    selection_mode: str | tuple[str, ...] | None = None,
    on_select: str = "rerun",
):
    """Render a figure in Streamlit; optionally enable point/box/lasso selection."""
    import streamlit as st

    kwargs = {"key": key, "use_container_width": use_container_width}
    if selection_mode is not None:
        kwargs["selection_mode"] = selection_mode
        kwargs["on_select"] = on_select
    return st.plotly_chart(fig, **kwargs)
