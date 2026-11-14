from __future__ import annotations

import pandas as pd
import streamlit as st


# Display a dataframe with an optional CSV export

def render_data_table(
    data: pd.DataFrame,
    *,
    title: str | None = None,
    key: str = "data_table",
    height: int = 420,
    download_label: str = "Descargar datos CSV",
    hide_index: bool = True,
) -> None:
    if title:
        st.subheader(title)

    if data.empty:
        st.info("No hay registros para los filtros seleccionados.")
        return

    st.dataframe(
        data,
        use_container_width=True,
        height=height,
        hide_index=hide_index,
    )

    csv_data = data.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    st.download_button(
        label=download_label,
        data=csv_data,
        file_name=f"{key}.csv",
        mime="text/csv",
        key=f"download_{key}",
    )
