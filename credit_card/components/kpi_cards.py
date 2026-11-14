from __future__ import annotations

from typing import Any
import streamlit as st


def format_currency(value: float, currency: str = "Q", decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{currency} {formatted}"


def format_number(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%".replace(".", ",")


# Render a responsive row of KPI cards

def render_kpi_cards(
    metrics: list[dict[str, Any]],
    *,
    columns: int = 4,
) -> None:
    if not metrics:
        st.info("No hay indicadores disponibles para la selección actual.")
        return

    columns = max(1, min(columns, len(metrics)))
    containers = st.columns(columns)

    for index, metric in enumerate(metrics):
        with containers[index % columns]:
            with st.container(border=True):
                st.caption(metric.get("label", "Indicador"))
                st.metric(
                    label=" ",
                    value=str(metric.get("value", "—")),
                    delta=metric.get("delta"),
                    delta_color=metric.get("delta_color", "normal"),
                    help=metric.get("help"),
                )
                if metric.get("footnote"):
                    st.caption(metric["footnote"])
