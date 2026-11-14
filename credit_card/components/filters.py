from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st


# Render shared filters; stable keys preserve selections across pages

def render_global_filters(
    data: pd.DataFrame,
    *,
    date_column: str = "fecha_corte",
    channel_column: str = "canal",
    risk_column: str = "banda_riesgo_originacion",
    partner_column: str = "id_aliado",
    show_partner: bool = True,
) -> dict[str, Any]:
    st.sidebar.subheader("Filtros globales")

    filters: dict[str, Any] = {}

    if date_column in data.columns:
        dates = pd.to_datetime(data[date_column], errors="coerce").dropna().sort_values().unique()
        date_options = [pd.Timestamp(value) for value in dates]
        if date_options:
            default_date = date_options[-1]
            selected_date = st.sidebar.selectbox(
                "Mes de corte",
                options=date_options,
                index=len(date_options) - 1,
                format_func=lambda value: pd.Timestamp(value).strftime("%B %Y"),
                key="global_filter_cut_date",
            )
            filters[date_column] = pd.Timestamp(selected_date)

    if channel_column in data.columns:
        channel_options = sorted(data[channel_column].dropna().astype(str).unique().tolist())
        selected_channels = st.sidebar.multiselect(
            "Canal de adquisición",
            options=channel_options,
            default=channel_options,
            key="global_filter_channels",
        )
        filters[channel_column] = selected_channels

    if risk_column in data.columns:
        risk_options = data[risk_column].dropna().astype(str).unique().tolist()
        preferred_order = [value for value in ["A", "B", "C", "D", "E"] if value in risk_options]
        risk_options = preferred_order + [value for value in sorted(risk_options) if value not in preferred_order]
        selected_risks = st.sidebar.multiselect(
            "Banda de riesgo",
            options=risk_options,
            default=risk_options,
            key="global_filter_risk_bands",
        )
        filters[risk_column] = selected_risks

    if show_partner and partner_column in data.columns:
        partner_options = sorted(data[partner_column].dropna().astype(str).unique().tolist())
        selected_partners = st.sidebar.multiselect(
            "Aliado comercial",
            options=partner_options,
            default=partner_options,
            key="global_filter_partners",
        )
        filters[partner_column] = selected_partners

    if st.sidebar.button("Restablecer filtros", use_container_width=True):
        for key in [
            "global_filter_cut_date",
            "global_filter_channels",
            "global_filter_risk_bands",
            "global_filter_partners",
        ]:
            st.session_state.pop(key, None)
        st.rerun()

    return filters


# Apply the selected global filters without changing the source dataframe

def apply_global_filters(
    data: pd.DataFrame,
    filters: dict[str, Any],
) -> pd.DataFrame:
    filtered = data.copy()

    for column, selection in filters.items():
        if column not in filtered.columns:
            continue

        if column == "fecha_corte":
            dates = pd.to_datetime(filtered[column], errors="coerce")
            filtered = filtered.loc[dates == pd.Timestamp(selection)]
        elif isinstance(selection, list):
            if selection:
                filtered = filtered.loc[filtered[column].astype(str).isin(selection)]
            else:
                filtered = filtered.iloc[0:0]

    return filtered
