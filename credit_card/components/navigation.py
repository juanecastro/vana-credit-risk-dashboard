from __future__ import annotations

import streamlit as st


DEFAULT_PAGES = [
    ("credit_card/app.py", "Resumen ejecutivo", "house"),
    ("credit_card/pages/02_Portfolio_Analysis.py", "Análisis de cartera", "chart-line"),
    ("credit_card/pages/03_Vintage_Analysis.py", "Análisis de cosechas", "chart-area"),
    ("credit_card/pages/04_Risk_Segmentation.py", "Segmentación de riesgo", "shield-check"),
    ("credit_card/pages/05_Payment_Behavior.py", "Comportamiento de pago", "wallet"),
    ("credit_card/pages/06_Limit_Management.py", "Gestión de límites", "sliders-horizontal"),
    ("credit_card/pages/07_Growth_Simulator.py", "Simulador de crecimiento", "trending-up"),
    ("credit_card/pages/08_Recovery_Simulator.py", "Simulador de recuperación", "hand-coins"),
    ("credit_card/pages/09_Unit_Economics.py", "Economía unitaria", "calculator"),
]


def render_sidebar_navigation(pages: list[tuple[str, str, str]] | None = None) -> None:
    st.sidebar.title("VANA")
    st.sidebar.caption("Risk & Portfolio Intelligence")
    st.sidebar.divider()

    for page_path, label, icon in pages or DEFAULT_PAGES:
        st.sidebar.page_link(page_path, label=label, icon=f":material/{icon}:")


def render_page_header(title: str, description: str | None = None) -> None:
    st.title(title)
    if description:
        st.caption(description)
