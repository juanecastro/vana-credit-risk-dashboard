from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import hashlib

import numpy as np
import pandas as pd
import xlsxwriter
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = APP_DIR / "data" / "raw"

# Restrained institutional palette. Risk colors are muted and never used as the
# sole carrier of meaning; labels and values accompany every risk encoding.
C = {
    "navy": "#174A78", "blue": "#527A9E", "blue2": "#7895B0",
    "slate": "#8291A1", "teal": "#668A87", "green": "#6D8E7A",
    "amber": "#B08B52", "red": "#A96E6E", "ink": "#263548",
    "muted": "#52647A", "grid": "#E2E8EF", "bg": "#F4F6F9",
    "white": "#FFFFFF", "pale_blue": "#EAF0F6", "pale_red": "#F5EDEE",
    "pale_amber": "#F5F0E7", "pale_green": "#EAF1EC",
}
RISK_ORDER = ["A", "B", "C", "D", "E"]
PAYER_LABELS = {
    "TOTALERO": "Paga el total",
    "ENTRE_MINIMO_Y_TOTAL": "Entre mínimo y total",
    "PAGA_MINIMO": "Paga el mínimo",
    "MENOS_DEL_MINIMO": "Paga menos del mínimo",
    "NO_PAGA": "No realiza pago",
    "NUEVA_SIN_PAGO_EXIGIBLE": "Sin pago exigible",
    "SIN_SALDO": "Sin saldo",
}
LABELS = {
    "CROSS_SELL_VANA": "Venta cruzada Vana", "DIGITAL_ABIERTO": "Digital abierto",
    "ALIADO_COMERCIAL": "Aliado comercial", "METRO": "Metropolitana",
    "OCCIDENTE": "Occidente", "ORIENTE": "Oriente", "SUR": "Sur", "NORTE": "Norte",
    "SIN_HISTORIAL": "Sin historial de buró", "CON_HISTORIAL": "Con historial de buró",
    "INFORMAL": "Empleo informal", "FORMAL": "Empleo formal",
    "CONTACTADO": "Contactado", "NO_CONTACTADO": "No contactado",
    **PAYER_LABELS,
}


def label(value):
    if pd.isna(value):
        return "Sin dato"
    value = str(value)
    if re.fullmatch(r"AL\d+", value):
        return value
    return LABELS.get(value, value.replace("_", " ").title())


def fmt_num(value, decimals=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_money(value, decimals=0):
    if pd.isna(value):
        return "—"
    return "Q " + fmt_num(value, decimals)


def fmt_pct(value, decimals=1):
    if pd.isna(value):
        return "—"
    return (f"{value * 100:.{decimals}f}%").replace(".", ",")


def safe_div(a, b):
    return a / b if b not in (0, None) and pd.notna(b) else np.nan


@st.cache_data(show_spinner=False, max_entries=4)
def load_data(source_signature: str):
    """Load and normalize source data; signature invalidates cache on file changes."""
    del source_signature  # Used as a cache key, not as application data.
    accounts = pd.read_csv(RAW_DIR / "cuentas.csv")
    cuts = pd.read_csv(RAW_DIR / "cortes.csv")
    campaigns = pd.read_csv(RAW_DIR / "campanas_limite.csv", sep=";", encoding="utf-8-sig")
    for df in (accounts, cuts, campaigns):
        df["id_cuenta"] = df["id_cuenta"].astype(str).str.strip()
    accounts["fecha_apertura"] = pd.to_datetime(accounts["fecha_apertura"], errors="coerce")
    accounts["cosecha"] = accounts["fecha_apertura"].dt.to_period("M").astype(str)
    accounts["rango_edad"] = pd.cut(
        accounts["edad"], [0, 24, 34, 44, 54, 120],
        labels=["18–24", "25–34", "35–44", "45–54", "55+"], include_lowest=True,
    ).astype("object").fillna("Sin dato")
    cuts["fecha_corte"] = pd.to_datetime(cuts["fecha_corte"], errors="coerce")
    campaigns["corte_campana"] = pd.to_datetime(campaigns["corte_campana"], dayfirst=True, errors="coerce")
    for col in ["saldo_corte", "saldo_castigado", "limite", "limite_anterior", "dias_mora", "meses_en_libros", "score_comportamiento"]:
        if col in cuts:
            cuts[col] = pd.to_numeric(cuts[col], errors="coerce")
    return accounts, cuts, campaigns


def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;650;700;750&display=swap');
    :root {{ --vana-ink:{C['ink']}; --vana-muted:{C['muted']}; --vana-line:{C['grid']}; --vana-bg:{C['bg']}; }}
    html, body, [class*="css"] {{ font-family:Inter,Arial,sans-serif; color:{C['ink']}; }}
    .stApp {{ background:{C['bg']}; color:{C['ink']}; }}
    [data-testid="stHeader"] {{ background:{C['bg']}; height:1.25rem; }}
    [data-testid="stAppViewContainer"] .main .block-container {{ padding-top:1.05rem; padding-bottom:1.5rem; max-width:1600px; }}
    [data-testid="stSidebar"] {{ background:#FFFFFF; border-right:1px solid {C['grid']}; }}
    [data-testid="stSidebar"] > div:first-child {{ padding-top:.45rem; }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color:#43546B !important; font-size:11px; font-weight:650; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {{ background:#FFFFFF !important; border:1px solid #D7E0EA !important; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] * {{ color:{C['ink']} !important; }}
    /* Selected date/filter chips: BaseWeb text and icon foreground */
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {{
        background:#174A78 !important; border:1px solid #174A78 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"],
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] *,
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] span,
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] div {{
        color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] svg * {{
        fill:#FFFFFF !important; stroke:#FFFFFF !important; color:#FFFFFF !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"]:hover {{ background:#123B61 !important; }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color:{C['muted']} !important; }}
    [data-testid="stSidebar"] hr {{ border-color:{C['grid']}; margin:.55rem 0; }}
    [data-testid="stSidebar"] [data-testid="stExpander"] {{ border:0; }}
    h1,h2,h3 {{ color:{C['ink']} !important; letter-spacing:-.025em; }}
    h1 {{ font-size:1.72rem !important; font-weight:750 !important; margin:0 0 .1rem 0 !important; }}
    h2 {{ font-size:1.08rem !important; font-weight:700 !important; margin:.2rem 0 .1rem 0 !important; }}
    h3 {{ font-size:.96rem !important; font-weight:650 !important; }}
    p, li, [data-testid="stCaptionContainer"] p {{ color:{C['muted']}; font-size:13px !important; }}
    [data-testid="stWidgetLabel"] p {{ color:#43546B !important; }}
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{ background:#FFFFFF !important; border-color:#D7E0EA !important; }}
    div[data-baseweb="select"] *, div[data-baseweb="input"] input {{ color:{C['ink']} !important; }}
    [data-testid="stMetric"] {{ background:#FFFFFF; border:1px solid {C['grid']}; border-radius:9px; padding:11px 14px; min-height:83px; }}
    [data-testid="stMetricLabel"] {{ color:{C['muted']} !important; font-size:11px !important; }}
    [data-testid="stMetricValue"] {{ color:{C['ink']} !important; font-weight:750 !important; font-size:1.55rem !important; }}
    div[data-testid="stPlotlyChart"] {{ background:#FFFFFF; border:1px solid {C['grid']}; border-radius:9px; padding:3px; }}
    [data-testid="stDataFrame"] {{ border:1px solid {C['grid']}; border-radius:8px; }}
    [data-testid="stTabs"] button {{ font-weight:600; }}
    [data-testid="stVerticalBlock"] {{ gap:.68rem; }}
    [data-testid="stHorizontalBlock"] {{ gap:.85rem; }}
    .vana-banner {{ background:#FFFFFF; border:1px solid {C['grid']}; border-bottom:3px solid #597AF6; border-radius:8px; padding:12px 13px 10px; margin:0 0 13px 0; }}
    .vana-wordmark {{ color:#597AF6; font-size:30px; font-style:italic; font-weight:800; letter-spacing:-.055em; line-height:1; }}
    .vana-submark {{ color:{C['muted']}; font-size:8px; letter-spacing:.10em; text-transform:uppercase; margin-top:6px; }}
    .page-subtitle {{ font-size:14px; color:{C['muted']}; margin:0 0 7px 0; }}
    .section-subtitle {{ color:{C['muted']}; font-size:14px; margin:-3px 0 4px 0; }}
    .insight {{ background:#FFFFFF; border:1px solid {C['grid']}; border-left:3px solid {C['blue']}; border-radius:7px; padding:11px 13px; margin:5px 0; }}
    .insight strong {{ color:{C['ink']}; }}
    .insight p {{ margin:3px 0 0 0; font-size:13px; color:{C['muted']}; }}
    .muted-note {{ color:{C['muted']}; font-size:13px; }}
    .filter-heading {{ font-size:10px; font-weight:750; letter-spacing:.09em; color:#52647A; margin:2px 0 6px 0; }}
    button:focus-visible, input:focus-visible, [tabindex]:focus-visible {{ outline:3px solid {C['navy']} !important; outline-offset:2px !important; }}
    #MainMenu, footer {{ visibility:hidden; }}
    
</style>
    """, unsafe_allow_html=True)


def chart(fig, key, height=350):
    fig.update_layout(
        template="plotly_white", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": C["ink"], "size": 12},
        margin={"l": 48, "r": 28, "t": 34, "b": 42},
        hoverlabel={"bgcolor": "#FFFFFF", "font_color": C["ink"]},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0, "font": {"size": 11}},
    )
    fig.update_xaxes(showgrid=False, linecolor="#AAB7C6", tickfont={"size": 11, "color": C["muted"]}, title_font={"size": 12, "color": C["ink"]})
    fig.update_yaxes(gridcolor=C["grid"], zeroline=False, tickfont={"size": 11, "color": C["muted"]}, title_font={"size": 12, "color": C["ink"]})
    st.plotly_chart(fig, width="stretch", key=key, config={"displayModeBar": "hover", "displaylogo": False, "modeBarButtons": [["toImage"]], "toImageButtonOptions": {"format": "png", "filename": "vana_risk_chart", "height": 900, "width": 1600, "scale": 2}})


def section(title, description=None):
    st.subheader(title)
    if description:
        st.markdown(f'<div class="section-subtitle">{description}</div>', unsafe_allow_html=True)


def page_header(title, description, accounts, cuts, campaigns, selected_date, page_key):
    st.title(title)
    st.markdown(f'<div class="page-subtitle">{description}</div>', unsafe_allow_html=True)


def _source_fingerprint():
    digest = hashlib.sha256()
    for filename in ["cuentas.csv", "cortes.csv", "campanas_limite.csv", "diccionario.csv"]:
        path = RAW_DIR / filename
        digest.update(filename.encode())
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()[:16]


def _write_dataframe(workbook, sheet_name, frame):
    """Write a dataframe with minimal Excel overhead and no decorative formatting."""
    worksheet = workbook.add_worksheet(sheet_name)
    worksheet.write_row(0, 0, frame.columns.tolist())

    # Convert missing values to blank cells once, then stream rows to XlsxWriter.
    clean_frame = frame.astype(object).where(pd.notna(frame), None)
    for row_idx, row in enumerate(clean_frame.itertuples(index=False, name=None), start=1):
        worksheet.write_row(row_idx, 0, row)


@st.cache_data(show_spinner="Generando archivo Excel...", max_entries=4)
def build_export(_accounts, _cuts, _campaigns, selected_dates, page_key, filters, source_fingerprint):
    """Build a minimally formatted, reproducible workbook.

    DataFrames are excluded from Streamlit cache hashing: source_fingerprint,
    selected dates, page and filter metadata form the cache key instead.
    """
    output = BytesIO()
    selected_dates = sorted(pd.Timestamp(d) for d in selected_dates)
    ids = set(_accounts.id_cuenta.astype(str))
    raw_cuts = _cuts[
        _cuts.id_cuenta.astype(str).isin(ids)
        & _cuts.fecha_corte.isin(selected_dates)
    ].copy()
    account_cols = [column for column in _accounts.columns if column != "id_cuenta"]
    raw_data = raw_cuts.merge(
        _accounts[["id_cuenta", *account_cols]],
        on="id_cuenta",
        how="left",
        validate="many_to_one",
    )
    raw_campaigns = _campaigns[_campaigns.id_cuenta.astype(str).isin(ids)].copy()
    dictionary_path = RAW_DIR / "diccionario.csv"
    dictionary = (
        pd.read_csv(dictionary_path)
        if dictionary_path.exists()
        else pd.DataFrame(columns=["hoja", "campo", "descripcion"])
    )

    param_rows = [
        ("Fecha y hora de extracción", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Reporte", page_key),
        ("Fechas de corte seleccionadas", ", ".join(d.strftime("%Y-%m-%d") for d in selected_dates)),
        ("Cuentas incluidas", int(_accounts.id_cuenta.nunique())),
        ("Registros de corte incluidos", int(len(raw_data))),
        ("Asignaciones de campaña incluidas", int(len(raw_campaigns))),
        ("Versión de datos fuente", source_fingerprint),
    ]
    param_rows.extend((f"Filtro: {name}", value) for name, value in filters.items())
    params = pd.DataFrame(param_rows, columns=["Parámetro", "Valor"])

    frames = {
        "Parametros": params,
        "Datos": raw_data,
        "Campanas": raw_campaigns,
        "Diccionario": dictionary,
    }
    with xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_urls": False,
            "default_date_format": "yyyy-mm-dd",
        },
    ) as workbook:
        for sheet_name, frame in frames.items():
            _write_dataframe(workbook, sheet_name, frame)

    return output.getvalue()


def metric_row(items, cols=4):
    columns = st.columns(cols)
    for col, (name, value, delta) in zip(columns, items):
        with col:
            st.metric(name, value, delta=delta)


def _navigate_to(page):
    """Set the single source of truth for the currently displayed page."""
    st.session_state["vana_page"] = page


def sidebar(accounts, cuts, campaigns, pages, current):
    # Native Streamlit page links own navigation and active-page state.
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "vana_wordmark.svg"
    st.sidebar.image(str(logo_path), width=150)
    st.sidebar.header("ANÁLISIS DE CARTERA")
    for page_title in ["Key Metrics", "Portafolio", "Riesgo de crédito"]:
        st.sidebar.page_link(pages[page_title], label=page_title)
    st.sidebar.header("GESTIÓN DE CARTERA")
    for page_title in ["Cobranza y límites", "Economía del portafolio"]:
        st.sidebar.page_link(pages[page_title], label=page_title)



    def multi(label_text, series, key, include_missing=False):
        values = [str(x) for x in series.dropna().unique()]
        if include_missing and series.isna().any():
            values.append("Sin aliado")
        values = sorted(set(values))
        return st.sidebar.multiselect(label_text, values, key=key, placeholder="Todos", format_func=label)

    selected = {
        "Canal": multi("Canal", accounts.canal, "f_channel"),
        "Aliado comercial": multi("Aliado comercial", accounts.id_aliado, "f_partner", True),
        "Región": multi("Región", accounts.region, "f_region"),
        "Banda de riesgo": multi("Banda de riesgo", accounts.banda_riesgo_originacion, "f_band"),
        "Cosecha": multi("Cosecha", accounts.cosecha, "f_vintage"),
        "Historial de buró": multi("Historial de buró", accounts.historial_buro, "f_bureau"),
        "Tipo de empleo": multi("Tipo de empleo", accounts.tipo_empleo, "f_employment"),
        "Rango de edad": multi("Rango de edad", accounts.rango_edad, "f_age"),
    }
    mask = pd.Series(True, index=accounts.index)
    filter_columns = {
        "Canal": "canal", "Aliado comercial": "id_aliado", "Región": "region",
        "Banda de riesgo": "banda_riesgo_originacion", "Cosecha": "cosecha",
        "Historial de buró": "historial_buro", "Tipo de empleo": "tipo_empleo", "Rango de edad": "rango_edad",
    }
    for display_name, vals in selected.items():
        col = filter_columns[display_name]
        if vals:
            if col == "id_aliado" and "Sin aliado" in vals:
                non_missing = [v for v in vals if v != "Sin aliado"]
                m = accounts[col].astype(str).isin(non_missing) if non_missing else pd.Series(False, index=accounts.index)
                m |= accounts[col].isna()
                mask &= m
            else:
                mask &= accounts[col].astype(str).isin(vals)
    filtered_accounts = accounts.loc[mask].copy()
    ids = set(filtered_accounts.id_cuenta)
    filtered_cuts = cuts[cuts.id_cuenta.isin(ids)].copy()
    filtered_campaigns = campaigns[campaigns.id_cuenta.isin(ids)].copy()

    dates = sorted(filtered_cuts.fecha_corte.dropna().unique())
    date_options = [pd.Timestamp(d) for d in dates]
    prior = st.session_state.get("f_cut_dates")
    valid_prior = [pd.Timestamp(d) for d in prior] if prior else date_options
    valid_prior = [d for d in valid_prior if d in date_options]
    selected_dates = st.sidebar.multiselect(
        "Fechas de corte", date_options, default=valid_prior or date_options,
        key="f_cut_dates", format_func=lambda d: pd.Timestamp(d).strftime("%b %Y").capitalize(),
        help="Selecciona uno o varios cortes mensuales disponibles. No existen datos diarios.")
    if not selected_dates:
        st.sidebar.warning("Selecciona al menos un corte.")
        return current, filtered_accounts.iloc[0:0], filtered_cuts.iloc[0:0], [], filtered_campaigns
    selected_dates = sorted(pd.Timestamp(d) for d in selected_dates)
    selected_date = selected_dates[-1]
    st.sidebar.caption(f"{len(selected_dates)} cortes · Referencia: {selected_date:%b %Y}")
    if st.sidebar.button("Restablecer filtros", width="stretch", key="reset_filters"):
        for key in ["f_channel", "f_partner", "f_region", "f_band", "f_vintage", "f_bureau", "f_employment", "f_age", "f_cut_dates"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("EXPORTACIONES")
    filter_metadata = {
        name: (", ".join(label(v) for v in vals) if vals else "Todos")
        for name, vals in selected.items()
    }
    filter_metadata["Fechas de corte"] = ", ".join(d.strftime("%Y-%m-%d") for d in selected_dates)
    st.sidebar.download_button(
        "Descargar Excel",
        data=lambda: build_export(filtered_accounts, filtered_cuts, filtered_campaigns, selected_dates, current, filter_metadata, _source_fingerprint()),
        file_name=f"vana_{re.sub(r'[^a-z0-9]+', '_', current.lower())}_{selected_date:%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch", key="export_sidebar_excel", on_click="ignore")
    st.sidebar.caption("Datos originales filtrados; sin agregados ni conclusiones.")
    return current, filtered_accounts, filtered_cuts, selected_dates, filtered_campaigns


@st.cache_data(show_spinner=False, max_entries=8)
def add_cohort_columns(cuts, accounts):
    data = cuts.merge(accounts[["id_cuenta", "fecha_apertura", "cosecha", "canal", "id_aliado", "region", "banda_riesgo_originacion", "score_originacion", "historial_buro", "tipo_empleo", "limite_inicial"]], on="id_cuenta", how="left", suffixes=("", "_account"))
    return data




def active_only(df):
    return df[df.estado.astype(str).str.upper().eq("ACTIVA")].copy()


def delinquency_bucket(df):
    return np.select(
        [df.estado.astype(str).str.upper().eq("CASTIGADA"), df.dias_mora.between(1, 29), df.dias_mora.between(30, 59),
         df.dias_mora.between(60, 89), df.dias_mora.between(90, 119), df.dias_mora.between(120, 149), df.dias_mora.between(150, 179)],
        ["Castigada", "1–29", "30–59", "60–89", "90–119", "120–149", "150–179"], default="Al día")


@st.cache_data(show_spinner=False, max_entries=8)
def monthly_portfolio(cuts, accounts):
    rows = []
    for date, g in cuts.groupby("fecha_corte"):
        a = active_only(g)
        ch = g[g.estado.astype(str).str.upper().eq("CASTIGADA")]
        bal = a.saldo_corte.sum()
        limit = a.limite.sum()
        bad = a[a.dias_mora.ge(30)]
        early = a[a.dias_mora.between(1, 29)]
        rows.append({
            "fecha_corte": date, "active_accounts": a.id_cuenta.nunique(), "active_balance": bal,
            "active_limit": limit, "utilization": safe_div(bal, limit),
            "dpd30_balance": bad.saldo_corte.sum(), "dpd30_balance_rate": safe_div(bad.saldo_corte.sum(), bal),
            "dpd30_accounts": bad.id_cuenta.nunique(), "dpd30_account_rate": safe_div(bad.id_cuenta.nunique(), a.id_cuenta.nunique()),
            "dpd1_29_balance": early.saldo_corte.sum(), "dpd1_29_rate": safe_div(early.saldo_corte.sum(), bal),
            "chargeoff_accounts": ch.id_cuenta.nunique(), "chargeoff_balance": ch.saldo_castigado.sum(),
            "new_accounts": accounts[accounts.fecha_apertura.dt.to_period("M").astype(str).eq(pd.Timestamp(date).to_period("M").strftime("%Y-%m"))].id_cuenta.nunique(),
        })
    result = pd.DataFrame(rows).sort_values("fecha_corte")
    result["cumulative_chargeoff"] = result.chargeoff_balance.cumsum()
    return result


@st.cache_data(show_spinner=False, max_entries=8)
def partner_metrics(data):
    active = active_only(data)
    active = active[active.canal.eq("ALIADO_COMERCIAL") & active.id_aliado.notna()].copy()
    if active.empty:
        return pd.DataFrame()
    active["bad_balance"] = np.where(active.dias_mora.ge(30), active.saldo_corte, 0)
    active["bad_account"] = active.dias_mora.ge(30).astype(int)
    total_bad = active.bad_balance.sum()
    out = active.groupby("id_aliado", as_index=False).agg(
        accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"),
        bad_balance=("bad_balance", "sum"), bad_accounts=("bad_account", "sum"))
    out["balance_rate"] = out.bad_balance / out.balance.replace(0, np.nan)
    out["account_rate"] = out.bad_accounts / out.accounts.replace(0, np.nan)
    out["share_of_partner_bad"] = out.bad_balance / total_bad if total_bad else np.nan
    out["bad_balance_contribution"] = out.bad_balance
    return out.sort_values(["bad_balance", "balance_rate"], ascending=[False, False])




@st.cache_data(show_spinner=False, max_entries=8)
def behavior_transitions(cuts):
    data = cuts.sort_values(["id_cuenta", "fecha_corte"]).copy()
    grp = data.groupby("id_cuenta", sort=False)
    data["next_date"] = grp.fecha_corte.shift(-1)
    data["next_state"] = grp.estado.shift(-1)
    data["next_dpd"] = grp.dias_mora.shift(-1)
    data["next_payer"] = grp.tipo_pagador.shift(-1)
    data["next_score"] = grp.score_comportamiento.shift(-1)
    month_gap = (data.next_date.dt.year - data.fecha_corte.dt.year) * 12 + data.next_date.dt.month - data.fecha_corte.dt.month
    data = data[month_gap.eq(1) & data.next_date.notna()].copy()
    data["next_30"] = data.next_state.astype(str).str.upper().eq("CASTIGADA") | (data.next_state.astype(str).str.upper().eq("ACTIVA") & data.next_dpd.ge(30))
    data["next_1plus"] = data.next_state.astype(str).str.upper().eq("CASTIGADA") | (data.next_state.astype(str).str.upper().eq("ACTIVA") & data.next_dpd.ge(1))
    data["payer_label"] = data.tipo_pagador.map(label)
    data["next_payer_label"] = data.next_payer.map(label)
    return data


@st.cache_data(show_spinner=False, max_entries=8)
def behavior_score_table(transitions):
    eligible = transitions[transitions.estado.astype(str).str.upper().eq("ACTIVA") & transitions.dias_mora.lt(30) & transitions.score_comportamiento.notna()].copy()
    if eligible.empty:
        return pd.DataFrame()
    bins = [0, 300, 600, 800, 950, 1000]
    labels = ["1–300", "301–600", "601–800", "801–950", "951–999"]
    eligible["score_band"] = pd.cut(eligible.score_comportamiento, bins=bins, labels=labels, include_lowest=True)
    out = eligible.groupby("score_band", observed=False).agg(
        observations=("id_cuenta", "size"), accounts=("id_cuenta", "nunique"),
        events_30=("next_30", "sum"), events_1plus=("next_1plus", "sum"),
    ).reset_index()
    out["rate_30"] = out.events_30 / out.observations.replace(0, np.nan)
    out["rate_1plus"] = out.events_1plus / out.observations.replace(0, np.nan)
    return out


@st.cache_data(show_spinner=False, max_entries=8)
def origination_score_table(all_data, selected_date):
    d = all_data[all_data.fecha_corte.le(selected_date)].copy()
    d["event"] = d.estado.astype(str).str.upper().eq("CASTIGADA") | (d.estado.astype(str).str.upper().eq("ACTIVA") & d.dias_mora.ge(30))
    d["current_bad"] = d.estado.astype(str).str.upper().eq("ACTIVA") & d.dias_mora.ge(30)
    account = d.sort_values("fecha_corte").groupby("id_cuenta", as_index=False).agg(
        banda=("banda_riesgo_originacion", "last"),
        ever_event=("event", "max"),
        current_bad=("current_bad", "last"),
        current_state=("estado", "last"),
    )
    account["is_active"] = account.current_state.astype(str).str.upper().eq("ACTIVA")
    out = account.groupby("banda", as_index=False).agg(
        accounts=("id_cuenta", "nunique"), ever_events=("ever_event", "sum"),
        active_accounts=("is_active", "sum"), active_bad=("current_bad", "sum"),
    )
    out["ever_event_rate"] = out.ever_events / out.accounts.replace(0, np.nan)
    out["active_bad_rate"] = out.active_bad / out.active_accounts.replace(0, np.nan)
    out["banda"] = pd.Categorical(out.banda, categories=RISK_ORDER, ordered=True)
    return out.sort_values("banda")


@st.cache_data(show_spinner=False, max_entries=8)
def vintage_tables(all_data):
    d = all_data.sort_values(["id_cuenta", "fecha_corte"]).copy()
    d["mob"] = pd.to_numeric(d.meses_en_libros, errors="coerce")
    d = d[d.mob.gt(0)].copy()
    active = active_only(d)
    active["bad_balance"] = np.where(active.dias_mora.ge(30), active.saldo_corte, 0)
    snap = active.groupby(["cosecha", "mob"], as_index=False).agg(
        accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), bad_balance=("bad_balance", "sum"))
    snap["bad_rate"] = snap.bad_balance / snap.balance.replace(0, np.nan)
    # Cumulative observed event incidence from the first available cut (May 2026).
    d["event"] = d.estado.astype(str).str.upper().eq("CASTIGADA") | (d.estado.astype(str).str.upper().eq("ACTIVA") & d.dias_mora.ge(30))
    d["ever_event"] = d.groupby("id_cuenta").event.cummax()
    cum = d.groupby(["cosecha", "mob"], as_index=False).agg(
        accounts_observed=("id_cuenta", "nunique"), accounts_ever_bad=("ever_event", "sum"))
    cum["ever_bad_rate"] = cum.accounts_ever_bad / cum.accounts_observed.replace(0, np.nan)
    return snap, cum


@st.cache_data(show_spinner=False, max_entries=8)
def campaign_analysis(campaigns, cuts, accounts, selected_date):
    assigned = campaigns[campaigns.corte_campana.lt(selected_date)].copy()
    if assigned.empty:
        return pd.DataFrame(), pd.DataFrame()
    assigned = assigned.merge(accounts[["id_cuenta", "canal", "id_aliado", "banda_riesgo_originacion", "cosecha", "region"]], on="id_cuenta", how="left")
    rows, segments = [], []
    for campaign_date, camp in assigned.groupby("corte_campana"):
        post_dates = sorted(cuts.loc[cuts.fecha_corte.gt(campaign_date) & cuts.fecha_corte.le(selected_date), "fecha_corte"].dropna().unique())
        if not post_dates:
            continue
        for target_date in post_dates:
            target = cuts[cuts.fecha_corte.eq(target_date)]
            cumulative = cuts[cuts.fecha_corte.gt(campaign_date) & cuts.fecha_corte.le(target_date)]
            event_state = cumulative.estado.astype(str).str.upper()
            dpd30_ids = set(cumulative.loc[event_state.eq("ACTIVA") & cumulative.dias_mora.ge(30), "id_cuenta"])
            chargeoff_ids = set(cumulative.loc[event_state.eq("CASTIGADA"), "id_cuenta"])
            events = dpd30_ids | chargeoff_ids
            for grp, g in camp.groupby("grupo"):
                ids = set(g.id_cuenta)
                obs = target[target.id_cuenta.isin(ids)]
                active = active_only(obs)
                bad_active = active[active.dias_mora.ge(30)]
                n = g.id_cuenta.nunique()
                rows.append({
                    "campaign_date": campaign_date, "target_date": target_date,
                    "horizon": (target_date.year - campaign_date.year) * 12 + target_date.month - campaign_date.month,
                    "group": grp, "assigned": n, "observed": obs.id_cuenta.nunique(),
                    "cumulative_events": len(ids & events), "itt_rate": len(ids & events) / n if n else np.nan,
                    "cumulative_dpd30": len(ids & dpd30_ids), "dpd30_rate": len(ids & dpd30_ids) / n if n else np.nan,
                    "cumulative_chargeoff": len(ids & chargeoff_ids), "chargeoff_rate": len(ids & chargeoff_ids) / n if n else np.nan,
                    "active_accounts": active.id_cuenta.nunique(),
                    "active_dpd30_rate": bad_active.id_cuenta.nunique() / active.id_cuenta.nunique() if active.id_cuenta.nunique() else np.nan,
                    "avg_balance": active.saldo_corte.mean() if not active.empty else np.nan,
                    "avg_utilization": (active.saldo_corte.sum() / active.limite.sum()) if active.limite.sum() else np.nan,
                })
        # Last observed horizon segment results, with original assignment as ITT denominator.
        final_date = post_dates[-1]
        final_target = cuts[cuts.fecha_corte.eq(final_date)]
        cumulative = cuts[cuts.fecha_corte.gt(campaign_date) & cuts.fecha_corte.le(final_date)]
        event_state = cumulative.estado.astype(str).str.upper()
        dpd30_ids = set(cumulative.loc[event_state.eq("ACTIVA") & cumulative.dias_mora.ge(30), "id_cuenta"])
        chargeoff_ids = set(cumulative.loc[event_state.eq("CASTIGADA"), "id_cuenta"])
        events = dpd30_ids | chargeoff_ids
        for segment_col in ["banda_riesgo_originacion", "tipo_pagador_en_campana", "canal", "id_aliado"]:
            for (grp, seg), g in camp.groupby(["grupo", segment_col], dropna=False):
                ids = set(g.id_cuenta)
                segments.append({
                    "campaign_date": campaign_date, "group": grp, "segment_type": segment_col,
                    "segment": "Sin dato" if pd.isna(seg) else label(seg), "assigned": len(ids),
                    "events": len(ids & events), "itt_rate": len(ids & events) / len(ids) if ids else np.nan,
                })
    return pd.DataFrame(rows), pd.DataFrame(segments)


@st.cache_data(show_spinner=False, max_entries=8)
def limit_metrics(cuts):
    rows = []
    for date, g in cuts.groupby("fecha_corte"):
        a = active_only(g)
        increases = g[g.aumento_limite_en_corte.astype(str).str.upper().eq("SI")]
        rows.append({
            "fecha_corte": date, "active_accounts": a.id_cuenta.nunique(), "active_limit": a.limite.sum(),
            "avg_limit": a.limite.mean(), "balance": a.saldo_corte.sum(),
            "utilization": safe_div(a.saldo_corte.sum(), a.limite.sum()),
            "accounts_increased": increases.id_cuenta.nunique(),
            "increase_amount": (increases.limite - increases.limite_anterior).clip(lower=0).sum(),
        })
    return pd.DataFrame(rows).sort_values("fecha_corte")




def executive_page(accounts, cuts, campaigns, selected_date, selected_dates):
    all_data = add_cohort_columns(cuts, accounts)
    snap = all_data[all_data.fecha_corte.eq(selected_date)]
    active = active_only(snap)
    if active.empty:
        st.info("No hay cuentas activas para la selección actual."); return
    hist = monthly_portfolio(cuts, accounts)
    hist = hist[hist.fecha_corte.isin(selected_dates)]
    cur = hist[hist.fecha_corte.eq(selected_date)].iloc[-1]
    page_header("Key Metrics", "Estado y evolución del portafolio de tarjeta de crédito.", accounts, cuts, campaigns, selected_date, "resumen")
    metric_row([
        ("Saldo activo", fmt_money(cur.active_balance / 1e6, 1) + "M", None),
        ("Mora 30+ sobre saldo", fmt_pct(cur.dpd30_balance_rate), None),
        ("Cuentas activas", fmt_num(cur.active_accounts), None),
        ("Utilización", fmt_pct(cur.utilization), None),
    ])
    left, right = st.columns([1.25, 1])
    with left:
        section("Evolución de la mora", "Tasas sobre saldo activo al cierre de cada corte; castigos se muestran por separado.")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.fecha_corte, y=hist.dpd1_29_rate, name="1–29 días", mode="lines+markers", line={"color": C["amber"], "width": 2.4}))
        fig.add_trace(go.Scatter(x=hist.fecha_corte, y=hist.dpd30_balance_rate, name="30+ días", mode="lines+markers", line={"color": C["red"], "width": 2.7}))
        fig.add_hline(y=.10, line_dash="dot", line_color=C["slate"], annotation_text="Referencia 10%")
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        chart(fig, "exec_delinquency", 340)
    with right:
        section("Distribución de cartera por mora", "Saldo activo por altura de mora; los castigados no forman parte del saldo activo.")
        d = active.copy(); d["bucket"] = delinquency_bucket(d)
        order = ["Al día", "1–29", "30–59", "60–89", "90–119", "120–149", "150–179"]
        dist = d.groupby("bucket", as_index=False).agg(balance=("saldo_corte", "sum"), accounts=("id_cuenta", "nunique"))
        dist = dist[dist.bucket.isin(order)].copy(); dist["share"] = dist.balance / dist.balance.sum()
        dist["bucket"] = pd.Categorical(dist.bucket, categories=order, ordered=True); dist = dist.sort_values("bucket")
        fig = go.Figure(go.Bar(x=dist.share, y=dist.bucket.astype(str), orientation="h", marker_color=[C["green"] if x == "Al día" else C["amber"] if x == "1–29" else C["red"] for x in dist.bucket.astype(str)], text=dist.share.map(fmt_pct), textposition="outside", customdata=dist[["accounts", "balance"]], hovertemplate="Tramo: %{y}<br>Participación: %{x:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Saldo: Q %{customdata[1]:,.0f}<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, max(.1, dist.share.max() * 1.25)])
        chart(fig, "exec_dpd_distribution", 340)
    section("Castigos de cartera", "Flujo mensual de saldo castigado; no se suma al saldo activo.")
    fig = go.Figure(go.Bar(x=hist.fecha_corte, y=hist.chargeoff_balance, marker_color=C["slate"], text=[fmt_money(x) if x else "—" for x in hist.chargeoff_balance], textposition="outside"))
    fig.update_yaxes(tickprefix="Q ", tickformat=",.0f", rangemode="tozero")
    chart(fig, "exec_chargeoffs", 290)
    section("Diagnóstico mensual de mora", "Separa indicadores de stock (tasas al cierre) de flujo (castigos registrados durante el mes).")
    diag = hist.copy()
    diag["Mora 30+ / saldo"] = diag.dpd30_balance_rate.map(fmt_pct)
    diag["Mora 30+ / cuentas"] = diag.dpd30_account_rate.map(fmt_pct)
    diag["Mora 1–29 / saldo"] = diag.dpd1_29_rate.map(fmt_pct)
    diag["Castigos del mes"] = diag.chargeoff_balance.map(fmt_money)
    diag["Saldo activo"] = diag.active_balance.map(fmt_money)
    st.dataframe(diag[["fecha_corte", "active_accounts", "Saldo activo", "Mora 30+ / saldo", "Mora 30+ / cuentas", "Mora 1–29 / saldo", "Castigos del mes"]].rename(columns={"fecha_corte": "Corte", "active_accounts": "Cuentas activas"}), width="stretch", hide_index=True)


def portfolio_page(accounts, cuts, campaigns, selected_date, selected_dates):
    data = add_cohort_columns(cuts, accounts)
    snap = data[data.fecha_corte.eq(selected_date)]
    active = active_only(snap)
    hist = monthly_portfolio(cuts, accounts)
    hist = hist[hist.fecha_corte.isin(selected_dates)]
    page_header("Portafolio", "Evolución de exposición, originación, utilización y composición de la cartera.", accounts, cuts, campaigns, selected_date, "portafolio")
    if active.empty:
        st.info("No hay cuentas activas para la selección actual."); return
    cur = hist[hist.fecha_corte.eq(selected_date)].iloc[-1]
    metric_row([("Cuentas activas", fmt_num(cur.active_accounts), None), ("Saldo activo", fmt_money(cur.active_balance / 1e6, 1) + "M", None), ("Límite activo", fmt_money(cur.active_limit / 1e6, 1) + "M", None), ("Utilización", fmt_pct(cur.utilization), None)])
    left, right = st.columns(2)
    with left:
        section("Evolución del saldo activo", "Saldo de cuentas activas al cierre de cada mes.")
        fig = go.Figure(go.Scatter(x=hist.fecha_corte, y=hist.active_balance, mode="lines+markers", line={"color": C["navy"], "width": 2.8}, fill="tozeroy", fillcolor="rgba(82,122,158,.10)"))
        fig.update_yaxes(tickprefix="Q ", tickformat=",.0f")
        chart(fig, "port_balance", 320)
    with right:
        section("Evolución de cuentas activas", "Número de cuentas vigentes por corte.")
        fig = go.Figure(go.Scatter(x=hist.fecha_corte, y=hist.active_accounts, mode="lines+markers", line={"color": C["blue"], "width": 2.8}))
        fig.update_yaxes(tickformat=",.0f")
        chart(fig, "port_accounts", 320)
    left, right = st.columns(2)
    with left:
        section("Originación de nuevas cuentas", "Cuentas abiertas por mes y canal de adquisición.")
        origin = accounts[accounts.fecha_apertura.le(selected_date)].groupby(["cosecha", "canal"], as_index=False).agg(accounts=("id_cuenta", "nunique"))
        origin["channel_label"] = origin.canal.map(label)
        fig = px.bar(origin, x="cosecha", y="accounts", color="channel_label", barmode="stack", color_discrete_map={"Venta cruzada Vana": C["navy"], "Digital abierto": C["blue"], "Aliado comercial": C["slate"]})
        fig.update_layout(xaxis_title="Cosecha", yaxis_title="Cuentas", legend_title=None)
        chart(fig, "port_originations", 330)
    with right:
        section("Composición regional", "Saldo activo y número de cuentas por región.")
        reg = active.groupby("region", as_index=False).agg(balance=("saldo_corte", "sum"), accounts=("id_cuenta", "nunique")).sort_values("balance")
        reg["region_label"] = reg.region.map(label)
        fig = go.Figure(go.Bar(x=reg.balance, y=reg.region_label, orientation="h", marker_color=C["blue"], text=reg.balance.map(fmt_money), textposition="outside", customdata=reg[["accounts"]], hovertemplate="Región: %{y}<br>Saldo: Q %{x:,.0f}<br>Cuentas: %{customdata[0]:,.0f}<extra></extra>"))
        fig.update_xaxes(tickprefix="Q ", tickformat=",.0f")
        chart(fig, "port_region", 330)
    section("Composición por banda de riesgo", "Cuentas y saldo activo por banda de originación.")
    band = active.groupby("banda_riesgo_originacion", as_index=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"))
    band["banda_riesgo_originacion"] = pd.Categorical(band.banda_riesgo_originacion, categories=RISK_ORDER, ordered=True); band = band.sort_values("banda_riesgo_originacion")
    fig = go.Figure(go.Bar(x=band.banda_riesgo_originacion.astype(str), y=band.accounts, marker_color=C["blue"], text=band.accounts.map(fmt_num), textposition="outside", name="Cuentas"))
    fig.update_layout(xaxis_title="Banda de originación", yaxis_title="Cuentas")
    chart(fig, "port_risk_mix", 300)
    section("Límites y utilización", "Límite total, saldo y utilización del límite por corte.")
    lm = limit_metrics(cuts)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=lm.fecha_corte, y=lm.active_limit, name="Límite activo", mode="lines+markers", line={"color": C["navy"], "width": 2.5}))
    fig.add_trace(go.Scatter(x=lm.fecha_corte, y=lm.balance, name="Saldo activo", mode="lines+markers", line={"color": C["blue2"], "width": 2.5}))
    fig.update_yaxes(tickprefix="Q ", tickformat=",.0f")
    chart(fig, "port_limits", 320)


def risk_page(accounts, cuts, campaigns, selected_date, selected_dates):
    data = add_cohort_columns(cuts[cuts.fecha_corte.le(selected_date)], accounts)
    snap = data[data.fecha_corte.eq(selected_date)]
    active = active_only(snap)
    page_header("Riesgo de crédito", "Concentración por aliado, desempeño de scores y comparación de cosechas a igual MOB.", accounts, cuts, campaigns, selected_date, "riesgo")
    if active.empty:
        st.info("No hay cuentas activas para la selección actual."); return
    bad = active[active.dias_mora.ge(30)]
    metric_row([("Mora 30+ sobre saldo", fmt_pct(safe_div(bad.saldo_corte.sum(), active.saldo_corte.sum())), None), ("Mora 30+ por cuentas", fmt_pct(safe_div(bad.id_cuenta.nunique(), active.id_cuenta.nunique())), None), ("Saldo en mora 30+", fmt_money(bad.saldo_corte.sum() / 1e6, 2) + "M", None), ("Cuentas activas", fmt_num(active.id_cuenta.nunique()), None)])
    tab_partner, tab_score, tab_vintage = st.tabs(["Canal y aliados", "Scores", "Cosechas"])
    with tab_partner:
        section("Desempeño por canal", "Comparación de mora 30+ sobre saldo; revisar tamaño y composición de cada canal.")
        channel = active.copy(); channel["bad_balance"] = np.where(channel.dias_mora.ge(30), channel.saldo_corte, 0)
        ch = channel.groupby("canal", as_index=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), bad_balance=("bad_balance", "sum"))
        ch["rate"] = ch.bad_balance / ch.balance.replace(0, np.nan); ch["channel_label"] = ch.canal.map(label)
        ch = ch.sort_values("rate", ascending=False)
        fig = go.Figure(go.Bar(x=ch.rate, y=ch.channel_label, orientation="h", marker_color=C["blue"], text=ch.rate.map(fmt_pct), textposition="outside", customdata=ch[["accounts", "balance", "bad_balance"]], hovertemplate="Canal: %{y}<br>Mora 30+: %{x:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Saldo: Q %{customdata[1]:,.0f}<br>Saldo 30+: Q %{customdata[2]:,.0f}<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, max(.1, ch.rate.max() * 1.25)])
        chart(fig, "risk_channel", 270)
        partners = partner_metrics(snap)
        section("Ranking de aliados comerciales", "Ordenado por saldo en mora 30+; incluye tasa, volumen y contribución al saldo moroso del canal.")
        if partners.empty:
            st.info("No hay aliados comerciales para los filtros actuales.")
        else:
            top = partners.head(12).copy()
            fig = go.Figure(go.Bar(x=top.bad_balance, y=top.id_aliado, orientation="h", marker_color=C["red"], text=top.bad_balance.map(fmt_money), textposition="outside", customdata=top[["accounts", "balance_rate", "account_rate", "share_of_partner_bad"]], hovertemplate="Aliado: %{y}<br>Saldo 30+: Q %{x:,.0f}<br>Cuentas: %{customdata[0]:,.0f}<br>Mora sobre saldo: %{customdata[1]:.1%}<br>Mora por cuentas: %{customdata[2]:.1%}<br>Contribución al saldo moroso de aliados: %{customdata[3]:.1%}<extra></extra>"))
            fig.update_xaxes(tickprefix="Q ", tickformat=",.0f")
            chart(fig, "risk_partner_rank", 410)
            display = partners.copy()
            for col in ["balance_rate", "account_rate", "share_of_partner_bad"]:
                display[col] = display[col].map(fmt_pct)
            display["balance"] = display.balance.map(fmt_money); display["bad_balance"] = display.bad_balance.map(fmt_money)
            display = display.rename(columns={"id_aliado": "Aliado", "accounts": "Cuentas", "balance": "Saldo", "bad_balance": "Saldo 30+", "balance_rate": "Mora / saldo", "account_rate": "Mora / cuentas", "share_of_partner_bad": "% mora aliados"})
            st.dataframe(display[["Aliado", "Cuentas", "Saldo", "Saldo 30+", "Mora / saldo", "Mora / cuentas", "% mora aliados"]], width="stretch", hide_index=True)
            section("Mora por aliado dentro de banda de originación", "Permite comparar aliados con una composición de score más homogénea; interpretar con el tamaño de muestra.")
            detail = active[active.canal.eq("ALIADO_COMERCIAL") & active.id_aliado.notna()].copy()
            detail["bad"] = np.where(detail.dias_mora.ge(30), detail.saldo_corte, 0)
            cross = detail.groupby(["id_aliado", "banda_riesgo_originacion"], as_index=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), bad=("bad", "sum"))
            cross["rate"] = cross.bad / cross.balance.replace(0, np.nan)
            cross = cross[cross.accounts.ge(25)]
            if not cross.empty:
                selected_partners = partners.head(10).id_aliado.tolist()
                cross = cross[cross.id_aliado.isin(selected_partners)]
                matrix = cross.pivot(index="id_aliado", columns="banda_riesgo_originacion", values="rate").reindex(columns=RISK_ORDER)
                counts = cross.pivot(index="id_aliado", columns="banda_riesgo_originacion", values="accounts").reindex(index=matrix.index, columns=matrix.columns)
                labels = np.empty(matrix.shape, dtype=object)
                for i in range(matrix.shape[0]):
                    for j in range(matrix.shape[1]):
                        v = matrix.iloc[i, j]
                        n = counts.iloc[i, j]
                        labels[i, j] = f"{fmt_pct(v)}\n(n={fmt_num(n)})" if pd.notna(v) and pd.notna(n) else "—"
                fig = go.Figure(go.Heatmap(z=matrix.values, x=matrix.columns.astype(str), y=matrix.index.astype(str),
                    colorscale=[[0, "#F0F3F6"], [.55, "#AABBC9"], [1, C["navy"]]], colorbar={"title": "Mora 30+", "tickformat": ".0%"},
                    text=labels, texttemplate="%{text}", hovertemplate="Aliado: %{y}<br>Banda: %{x}<br>Mora 30+: %{z:.1%}<extra></extra>"))
                fig.update_layout(height=max(340, 34 * len(matrix.index)), xaxis_title="Banda de originación", yaxis_title="Aliado")
                chart(fig, "risk_partner_within_band", max(340, 34 * len(matrix.index)))
                st.caption("Top 10 aliados por saldo moroso. Se excluyen combinaciones con menos de 25 cuentas; celdas sin dato no alcanzan ese umbral.")
                section("Desempeño del aliado por MOB", "Comparación de mora 30+ sobre saldo a igual antigüedad de cuenta; cada celda incluye solo observaciones con al menos 25 cuentas.")
                partner_history = data[data.canal.eq("ALIADO_COMERCIAL") & data.id_aliado.isin(selected_partners)].copy()
                partner_history = active_only(partner_history)
                partner_history["bad_balance"] = np.where(partner_history.dias_mora.ge(30), partner_history.saldo_corte, 0)
                partner_history["meses_en_libros"] = pd.to_numeric(partner_history["meses_en_libros"], errors="coerce")
                partner_history = partner_history[partner_history.meses_en_libros.gt(0)]
                pm = partner_history.groupby(["id_aliado", "meses_en_libros"], as_index=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), bad=("bad_balance", "sum"))
                pm = pm[pm.accounts.ge(25)]
                pm["rate"] = pm.bad / pm.balance.replace(0, np.nan)
                if not pm.empty:
                    pm_matrix = pm.pivot(index="id_aliado", columns="meses_en_libros", values="rate").sort_index()
                    fig = go.Figure(go.Heatmap(z=pm_matrix.values, x=pm_matrix.columns.astype(str), y=pm_matrix.index.astype(str), colorscale=[[0, "#F0F3F6"], [.55, "#AABBC9"], [1, C["navy"]]], colorbar={"title": "Mora 30+", "tickformat": ".0%"}, text=np.vectorize(lambda x: fmt_pct(x) if pd.notna(x) else "—")(pm_matrix.values), texttemplate="%{text}", hovertemplate="Aliado: %{y}<br>MOB: %{x}<br>Mora 30+: %{z:.1%}<extra></extra>"))
                    fig.update_layout(height=max(340, 34 * len(pm_matrix.index)), xaxis_title="Meses en libros (MOB)", yaxis_title="Aliado")
                    chart(fig, "risk_partner_mob", max(340, 34 * len(pm_matrix.index)))
                selected_partner = st.selectbox("Consultar cuentas de un aliado", selected_partners, key="partner_account_drilldown")
                partner_accounts = active[active.id_aliado.eq(selected_partner)].copy()
                partner_accounts["Utilización"] = partner_accounts.saldo_corte / partner_accounts.limite.replace(0, np.nan)
                partner_accounts = partner_accounts.sort_values(["dias_mora", "saldo_corte"], ascending=[False, False])
                drill = partner_accounts[["id_cuenta", "banda_riesgo_originacion", "score_originacion", "score_comportamiento", "saldo_corte", "limite", "Utilización", "dias_mora", "tipo_pagador", "meses_en_libros"]].copy()
                drill["saldo_corte"] = drill.saldo_corte.map(fmt_money); drill["limite"] = drill.limite.map(fmt_money); drill["Utilización"] = drill["Utilización"].map(fmt_pct)
                drill = drill.rename(columns={"id_cuenta": "Cuenta", "banda_riesgo_originacion": "Banda", "score_originacion": "Score originación", "score_comportamiento": "Score comportamiento", "saldo_corte": "Saldo", "limite": "Límite", "dias_mora": "Días de mora", "tipo_pagador": "Tipo de pagador", "meses_en_libros": "MOB"})
                st.dataframe(drill, width="stretch", hide_index=True)
    with tab_score:
        section("Desempeño del score de originación", "Mayor score significa menor riesgo. Las métricas se separan para distinguir historial observado y situación actual.")
        orig = origination_score_table(data, selected_date)
        left, right = st.columns(2)
        with left:
            section("Incidencia histórica de mora 30+ o castigo", "Cuentas con al menos un evento desde mayo de 2026 / todas las cuentas de la banda.")
            fig = go.Figure(go.Bar(x=orig.banda.astype(str), y=orig.ever_event_rate, marker_color=C["blue"], text=orig.ever_event_rate.map(fmt_pct), textposition="outside", customdata=orig[["accounts", "ever_events"]], hovertemplate="Banda: %{x}<br>Incidencia observada: %{y:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Cuentas con evento: %{customdata[1]:,.0f}<extra></extra>"))
            fig.update_yaxes(tickformat=".0%", rangemode="tozero")
            chart(fig, "risk_origination_historical", 330)
        with right:
            section("Mora 30+ actual", "Cuentas activas con mora 30+ / todas las cuentas activas de la banda en el corte seleccionado.")
            fig = go.Figure(go.Bar(x=orig.banda.astype(str), y=orig.active_bad_rate, marker_color=C["red"], text=orig.active_bad_rate.map(fmt_pct), textposition="outside", customdata=orig[["active_accounts", "active_bad"]], hovertemplate="Banda: %{x}<br>Mora 30+ actual: %{y:.1%}<br>Cuentas activas: %{customdata[0]:,.0f}<br>Cuentas activas en mora: %{customdata[1]:,.0f}<extra></extra>"))
            fig.update_yaxes(tickformat=".0%", rangemode="tozero")
            chart(fig, "risk_origination_current", 330)
        orig_show = orig.copy(); orig_show["Incidencia histórica"] = orig_show.ever_event_rate.map(fmt_pct); orig_show["Mora 30+ actual"] = orig_show.active_bad_rate.map(fmt_pct)
        st.dataframe(orig_show[["banda", "accounts", "ever_events", "Incidencia histórica", "active_accounts", "active_bad", "Mora 30+ actual"]].rename(columns={"banda": "Banda", "accounts": "Cuentas observadas", "ever_events": "Cuentas con evento", "active_accounts": "Cuentas activas", "active_bad": "Activas con mora 30+"}), width="stretch", hide_index=True)
        st.caption("La incidencia histórica considera al menos un corte con 30+ días o castigo desde mayo de 2026; su denominador son todas las cuentas observadas. La mora actual usa únicamente cuentas activas en el corte seleccionado. Las cuentas originadas antes de mayo tienen historial incompleto. La política de cutoff cambió de 600 hasta mayo a 560 desde junio de 2026; interpreta la banda E junto con cosecha y MOB.")
        transitions = behavior_transitions(cuts[cuts.fecha_corte.le(selected_date)])
        bs = behavior_score_table(transitions)
        section("Desempeño del score de comportamiento", "Evento en el siguiente corte mensual: entrada a 30+ días o castigo. La base incluye cuentas activas con menos de 30 días de mora y score disponible.")
        if bs.empty:
            st.info("No hay transiciones mensuales consecutivas elegibles para evaluar el score de comportamiento.")
        else:
            fig = go.Figure(go.Bar(x=bs.score_band.astype(str), y=bs.rate_30, marker_color=C["navy"], text=bs.rate_30.map(fmt_pct), textposition="outside", customdata=bs[["observations", "events_30"]], hovertemplate="Score: %{x}<br>Evento 30+ / castigo: %{y:.1%}<br>Observaciones: %{customdata[0]:,.0f}<br>Eventos: %{customdata[1]:,.0f}<extra></extra>"))
            fig.update_yaxes(tickformat=".0%", rangemode="tozero")
            chart(fig, "risk_behavior_score", 330)
            show = bs.copy(); show["Tasa 30+ / castigo"] = show.rate_30.map(fmt_pct); show["Tasa 1+"] = show.rate_1plus.map(fmt_pct)
            st.dataframe(show[["score_band", "observations", "events_30", "Tasa 30+ / castigo", "Tasa 1+"]].rename(columns={"score_band": "Banda de score", "observations": "Observaciones", "events_30": "Eventos 30+ / castigo"}), width="stretch", hide_index=True)
            st.caption("Las observaciones son cuenta-mes; una misma cuenta puede aparecer en más de un mes. No interpretar como una muestra de cuentas únicas.")
    with tab_vintage:
        section("Evolución de mora 30+ por cosecha y MOB", "Cada línea representa una cosecha; la comparación se realiza a igual antigüedad desde apertura.")
        full = add_cohort_columns(cuts[cuts.fecha_corte.le(selected_date)], accounts)
        snap_v, cum_v = vintage_tables(full)
        if snap_v.empty:
            st.info("No hay datos suficientes para comparar cosechas.")
        else:
            available_vintages = sorted(snap_v.cosecha.dropna().unique())
            default_vintages = available_vintages[-5:] if len(available_vintages) > 5 else available_vintages
            chosen_vintages = st.multiselect("Cosechas a comparar", available_vintages, default=default_vintages, key="vintage_line_selection")
            line_data = snap_v[snap_v.cosecha.isin(chosen_vintages)].sort_values(["cosecha", "mob"])
            if line_data.empty:
                st.info("Selecciona al menos una cosecha.")
            else:
                fig = go.Figure()
                for vintage, group in line_data.groupby("cosecha", sort=True):
                    fig.add_trace(go.Scatter(x=group.mob, y=group.bad_rate, mode="lines+markers", name=vintage,
                                             line={"width": 2.2}, customdata=group[["accounts", "balance"]],
                                             hovertemplate="Cosecha: " + str(vintage) + "<br>MOB: %{x}<br>Mora 30+ sobre saldo: %{y:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Saldo: Q %{customdata[1]:,.0f}<extra></extra>"))
                fig.update_xaxes(title="Meses en libros (MOB)", dtick=1)
                fig.update_yaxes(title="Mora 30+ sobre saldo", tickformat=".0%", rangemode="tozero")
                chart(fig, "risk_vintage_mob_lines", 390)

            section("Ranking de cosechas al mismo MOB", "Compara las cosechas que tienen observaciones en el MOB seleccionado; se muestran tasa y tamaño de muestra.")
            common = snap_v[snap_v.cosecha.isin(chosen_vintages)]
            common_mobs = sorted(common.groupby("mob").cosecha.nunique().loc[lambda x: x >= 2].index.tolist())
            if common_mobs:
                default_mob = common_mobs[-1]
                selected_mob = st.selectbox("MOB de comparación", common_mobs, index=common_mobs.index(default_mob), key="vintage_common_mob")
                ranked = common[common.mob.eq(selected_mob)].sort_values("bad_rate", ascending=False).copy()
                fig = go.Figure(go.Bar(x=ranked.bad_rate, y=ranked.cosecha, orientation="h", marker_color=C["blue"],
                                       text=ranked.bad_rate.map(fmt_pct), textposition="outside",
                                       customdata=ranked[["accounts", "balance"]],
                                       hovertemplate="Cosecha: %{y}<br>MOB: " + str(selected_mob) + "<br>Mora 30+: %{x:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Saldo: Q %{customdata[1]:,.0f}<extra></extra>"))
                fig.update_xaxes(title="Mora 30+ sobre saldo", tickformat=".0%", rangemode="tozero")
                chart(fig, "risk_vintage_same_mob_rank", max(280, 34 * len(ranked)))
                ranked_show = ranked[["cosecha", "accounts", "bad_rate", "balance"]].copy()
                ranked_show["bad_rate"] = ranked_show.bad_rate.map(fmt_pct)
                ranked_show["balance"] = ranked_show.balance.map(fmt_money)
                st.dataframe(ranked_show.rename(columns={"cosecha": "Cosecha", "accounts": "Cuentas", "bad_rate": "Mora 30+ / saldo", "balance": "Saldo"}), width="stretch", hide_index=True)
            else:
                st.info("No hay al menos dos cosechas con observaciones en un mismo MOB para la selección actual.")

            section("Incidencia acumulada observada por cosecha", "Porcentaje de cuentas que registraron 30+ o castigo desde el primer corte disponible; no representa incidencia de vida completa.")
            cumulative_data = cum_v[cum_v.cosecha.isin(chosen_vintages)].sort_values(["cosecha", "mob"])
            fig = go.Figure()
            for vintage, group in cumulative_data.groupby("cosecha", sort=True):
                fig.add_trace(go.Scatter(x=group.mob, y=group.ever_bad_rate, mode="lines+markers", name=vintage,
                                         line={"width": 2.2}, customdata=group[["accounts_observed", "accounts_ever_bad"]],
                                         hovertemplate="Cosecha: " + str(vintage) + "<br>MOB: %{x}<br>Incidencia observada: %{y:.1%}<br>Cuentas observadas: %{customdata[0]:,.0f}<br>Cuentas con evento: %{customdata[1]:,.0f}<extra></extra>"))
            fig.update_xaxes(title="Meses en libros (MOB)", dtick=1)
            fig.update_yaxes(title="Incidencia acumulada observada", tickformat=".0%", rangemode="tozero")
            chart(fig, "risk_vintage_cumulative_lines", 390)
            st.caption("Las cosechas anteriores a mayo de 2026 tienen historia parcial. La incidencia acumulada solo se mide desde el primer corte disponible.")


def collections_page(accounts, cuts, campaigns, selected_date, selected_dates):
    data = add_cohort_columns(cuts, accounts)
    snap = data[data.fecha_corte.eq(selected_date)]
    active = active_only(snap)
    page_header("Cobranza y límites", "Pagadores, cobranza y desempeño de límites.", accounts, cuts, campaigns, selected_date, "cobranza_limites")
    if active.empty:
        st.info("No hay cuentas activas para la selección actual."); return
    transitions = behavior_transitions(cuts[cuts.fecha_corte.le(selected_date)])
    tab_payer, tab_collections, tab_campaign, tab_limits = st.tabs(["Pagadores y migración", "Gestión de cobranza", "Campañas de límites", "Gestión de líneas"])
    with tab_payer:
        section("Distribución por tipo de pagador", "Clasificación registrada en el corte seleccionado.")
        mix = active.groupby("tipo_pagador", as_index=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"))
        mix["payer_label"] = mix.tipo_pagador.map(label); mix = mix.sort_values("accounts", ascending=True)
        fig = go.Figure(go.Bar(x=mix.accounts, y=mix.payer_label, orientation="h", marker_color=C["blue"], text=mix.accounts.map(fmt_num), textposition="outside", customdata=mix[["balance"]], hovertemplate="Pagador: %{y}<br>Cuentas: %{x:,.0f}<br>Saldo: Q %{customdata[0]:,.0f}<extra></extra>"))
        chart(fig, "coll_payer_mix", 300)
        left, right = st.columns(2)
        with left:
            section("Riesgo posterior por tipo de pagador", "Entrada a mora 30+ o castigo en el siguiente corte, entre cuentas con menos de 30 días de mora al inicio.")
            elig = transitions[transitions.estado.astype(str).str.upper().eq("ACTIVA") & transitions.dias_mora.lt(30)]
            risk = elig.groupby("tipo_pagador", as_index=False).agg(observations=("id_cuenta", "size"), events=("next_30", "sum"))
            risk["rate"] = risk.events / risk.observations.replace(0, np.nan); risk["payer_label"] = risk.tipo_pagador.map(label); risk = risk.sort_values("rate")
            if not risk.empty:
                fig = go.Figure(go.Bar(x=risk.rate, y=risk.payer_label, orientation="h", marker_color=C["navy"], text=risk.rate.map(fmt_pct), textposition="outside", customdata=risk[["observations", "events"]], hovertemplate="Pagador: %{y}<br>Evento: %{x:.1%}<br>Observaciones: %{customdata[0]:,.0f}<br>Eventos: %{customdata[1]:,.0f}<extra></extra>"))
                fig.update_xaxes(tickformat=".0%", range=[0, max(.05, risk.rate.max() * 1.25)])
                chart(fig, "coll_payer_future", 320)
        with right:
            section("Migración entre tipos de pagador", "Transiciones de un corte mensual al siguiente; valores en porcentaje por tipo de pagador de origen.")
            trans = transitions[transitions.tipo_pagador.notna() & transitions.next_payer.notna()]
            if not trans.empty:
                matrix = pd.crosstab(trans.payer_label, trans.next_payer_label, normalize="index")
                fig = go.Figure(go.Heatmap(z=matrix.values, x=matrix.columns, y=matrix.index, colorscale=[[0, "#F1F4F7"], [.55, "#A6B8C8"], [1, C["navy"]]], colorbar={"title": "%"}, text=np.vectorize(fmt_pct)(matrix.values), texttemplate="%{text}", hovertemplate="Origen: %{y}<br>Destino: %{x}<br>Participación: %{z:.1%}<extra></extra>"))
                fig.update_layout(height=360, margin={"l": 140, "r": 20, "t": 30, "b": 100})
                chart(fig, "coll_payer_transition", 360)
        section("Riesgo latente entre cuentas al día en el último corte evaluable", "Porcentaje que presenta al menos 1 día de atraso o alcanza 30+ / castigo en el siguiente corte mensual.")
        # Latest origin cut with a subsequent observed month; October cannot be scored
        # forward because November is not present in the supplied data.
        latest_evaluable = transitions.fecha_corte.max() if not transitions.empty else pd.NaT
        latent = transitions[transitions.fecha_corte.eq(latest_evaluable) & transitions.estado.astype(str).str.upper().eq("ACTIVA") & transitions.dias_mora.eq(0)]
        latent_payer = latent.groupby("tipo_pagador", as_index=False).agg(observations=("id_cuenta", "size"), next_1plus=("next_1plus", "sum"), next_30=("next_30", "sum"))
        latent_payer["rate_1plus"] = latent_payer.next_1plus / latent_payer.observations.replace(0, np.nan)
        latent_payer["rate_30"] = latent_payer.next_30 / latent_payer.observations.replace(0, np.nan)
        latent_payer["payer_label"] = latent_payer.tipo_pagador.map(label)
        if not latent_payer.empty:
            st.caption(f"Último corte con seguimiento observado: {latest_evaluable:%B %Y}. No se estima riesgo futuro para octubre porque no existe un corte posterior en los datos.")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=latent_payer.payer_label, y=latent_payer.rate_1plus, name="Cualquier atraso (1+)", marker_color=C["amber"]))
            fig.add_trace(go.Bar(x=latent_payer.payer_label, y=latent_payer.rate_30, name="Mora 30+ / castigo", marker_color=C["red"]))
            fig.update_layout(barmode="group", xaxis_title=None, yaxis_title="Tasa en siguiente corte")
            fig.update_yaxes(tickformat=".0%")
            chart(fig, "coll_latent_risk", 340)
            st.dataframe(latent_payer.assign(**{"Atraso 1+": latent_payer.rate_1plus.map(fmt_pct), "30+ / castigo": latent_payer.rate_30.map(fmt_pct)})[["payer_label", "observations", "Atraso 1+", "30+ / castigo"]].rename(columns={"payer_label": "Tipo de pagador", "observations": "Observaciones"}), width="stretch", hide_index=True)
        else:
            st.info("No hay transiciones consecutivas para medir riesgo latente en la población seleccionada.")
        st.caption("Las observaciones son cuenta-mes y requieren dos cortes mensuales consecutivos. La selección de fechas puede reducir la muestra disponible.")
    with tab_collections:
        section("Resultado posterior a la gestión", "Cuentas con mora previa y gestión registrada en el mes; resultado observado en el corte seleccionado.")
        d = cuts.sort_values(["id_cuenta", "fecha_corte"]).copy()
        g = d.groupby("id_cuenta", sort=False)
        d["prev_date"] = g.fecha_corte.shift(1); d["prev_dpd"] = g.dias_mora.shift(1)
        prev_expected = d.fecha_corte - pd.offsets.MonthEnd(1)
        contact = d[d.fecha_corte.eq(selected_date) & d.prev_date.eq(prev_expected) & d.prev_dpd.gt(0) & d.gestion_cobranza_mes.isin(["CONTACTADO", "NO_CONTACTADO"])].copy()
        if contact.empty:
            st.info("No hay gestiones con mora previa y corte consecutivo para esta selección.")
        else:
            contact["resultado"] = np.select([contact.estado.astype(str).str.upper().eq("CASTIGADA"), contact.dias_mora.eq(0), contact.dias_mora.ge(30)], ["Castigada", "Al día", "30+ días"], default="1–29 días")
            tab = contact.groupby(["gestion_cobranza_mes", "resultado"], as_index=False).agg(accounts=("id_cuenta", "nunique"))
            tab["share"] = tab.accounts / tab.groupby("gestion_cobranza_mes").accounts.transform("sum")
            tab["gestion_label"] = tab.gestion_cobranza_mes.map(label)
            fig = px.bar(tab, x="share", y="resultado", color="gestion_label", orientation="h", barmode="group", text=tab.share.map(fmt_pct), custom_data=["accounts"], color_discrete_map={"Contactado": C["navy"], "No contactado": C["slate"]})
            fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="Resultado: %{y}<br>Gestión: %{fullData.name}<br>Participación: %{x:.1%}<br>Cuentas: %{customdata[0]:,.0f}<extra></extra>")
            fig.update_xaxes(tickformat=".0%", range=[0, 1.18])
            fig.update_layout(margin={"l": 90, "r": 40, "t": 35, "b": 45}, legend_title=None)
            chart(fig, "coll_contact_result", 380)
            st.caption("Comparación descriptiva, no causal: el contacto puede dirigirse a cuentas de mayor riesgo.")
    with tab_campaign:
        section("Campañas de aumento de límite", "Riesgo acumulado: tratamiento vs. control.")
        follow, segments = campaign_analysis(campaigns, cuts, accounts, selected_date)
        if follow.empty:
            st.info("No hay cortes posteriores a las campañas dentro de las fechas seleccionadas.")
        else:
            latest = follow.sort_values("target_date").groupby(["campaign_date", "group"], as_index=False).tail(1).copy()
            comparison_rows = []
            for camp_date, group in latest.groupby("campaign_date"):
                by_group = {str(r.group).upper(): r for r in group.itertuples()}
                control = by_group.get("CONTROL")
                treatment = by_group.get("TRATAMIENTO")
                if control is None or treatment is None:
                    continue
                n0, n1 = int(control.assigned), int(treatment.assigned)
                horizon = int(control.horizon)
                def risk_comparison(metric, count_metric):
                    p0, p1 = float(getattr(control, metric)), float(getattr(treatment, metric))
                    c0, c1 = int(getattr(control, count_metric)), int(getattr(treatment, count_metric))
                    diff = (p1 - p0) * 100
                    se = np.sqrt((p1 * (1-p1) / n1 if n1 else 0) + (p0 * (1-p0) / n0 if n0 else 0))
                    ci = f"{diff-1.96*se*100:+.1f} a {diff+1.96*se*100:+.1f} pp" if n0 and n1 else "—"
                    return c0, fmt_pct(p0), c1, fmt_pct(p1), f"{diff:+.1f} pp".replace(".", ","), ci.replace(".", ",")
                for metric_label, metric, count_metric in [
                    ("Mora 30+ acumulada", "dpd30_rate", "cumulative_dpd30"),
                    ("Castigo acumulado", "chargeoff_rate", "cumulative_chargeoff"),
                    ("Mora 30+ o castigo", "itt_rate", "cumulative_events"),
                ]:
                    c0, p0, c1, p1, diff, ci = risk_comparison(metric, count_metric)
                    comparison_rows.append({
                        "Campaña": pd.Timestamp(camp_date).strftime("%b %Y").capitalize(),
                        "Seguimiento": f"{horizon} meses",
                        "Indicador de riesgo": metric_label,
                        "Control (n)": f"{c0} / {n0}", "Riesgo control": p0,
                        "Tratamiento (n)": f"{c1} / {n1}", "Riesgo tratamiento": p1,
                        "Diferencia T − C": diff, "IC 95% diferencia": ci,
                    })
            section("Riesgo acumulado", "Tasas sobre las cuentas originalmente asignadas.")
            if comparison_rows:
                st.dataframe(pd.DataFrame(comparison_rows), width="stretch", hide_index=True)
                st.caption("Mora 30+ y castigo se muestran por separado; la fila combinada cuenta cuentas únicas. Diferencia: tratamiento − control; IC 95% aproximado.")
            section("Estado actual de cuentas activas", "Último corte; solo cuentas activas.")
            current_rows = []
            for r in latest.itertuples():
                current_rows.append({
                    "Campaña": pd.Timestamp(r.campaign_date).strftime("%b %Y").capitalize(),
                    "Grupo": label(r.group), "Cuentas activas": int(r.active_accounts),
                    "Mora 30+ entre activas": fmt_pct(r.active_dpd30_rate),
                    "Saldo promedio": fmt_money(r.avg_balance),
                    "Utilización": fmt_pct(r.avg_utilization),
                })
            st.dataframe(pd.DataFrame(current_rows), width="stretch", hide_index=True)
            section("Balance inicial", "Corte anterior a cada campaña.")
            baseline_rows = []
            for camp_date, camp in campaigns[campaigns.corte_campana.lt(selected_date)].groupby("corte_campana"):
                prior_dates = sorted(cuts.loc[cuts.fecha_corte.lt(camp_date), "fecha_corte"].dropna().unique())
                if not prior_dates: continue
                base_date = prior_dates[-1]
                base = cuts[cuts.fecha_corte.eq(base_date)]
                for grp, assigned_group in camp.groupby("grupo"):
                    ids = set(assigned_group.id_cuenta)
                    b = base[base.id_cuenta.isin(ids)]
                    a = active_only(b)
                    baseline_rows.append({
                        "Campaña": pd.Timestamp(camp_date).strftime("%b %Y").capitalize(),
                        "Corte base": pd.Timestamp(base_date).strftime("%b %Y").capitalize(),
                        "Grupo": label(grp), "Cuentas asignadas": assigned_group.id_cuenta.nunique(),
                        "Cuentas observadas": b.id_cuenta.nunique(),
                        "Saldo promedio activo": fmt_money(a.saldo_corte.mean()),
                        "Utilización activa": fmt_pct(a.saldo_corte.sum()/a.limite.sum() if a.limite.sum() else np.nan),
                        "Mora 30+ entre activas": fmt_pct(a.loc[a.dias_mora.ge(30), "id_cuenta"].nunique()/a.id_cuenta.nunique() if a.id_cuenta.nunique() else np.nan),
                    })
            if baseline_rows:
                st.dataframe(pd.DataFrame(baseline_rows), width="stretch", hide_index=True)
            section("Riesgo por segmento", "Mora 30+ o castigo sobre cuentas asignadas.")
            if not segments.empty:
                seg = segments[segments.segment_type.isin(["banda_riesgo_originacion", "tipo_pagador_en_campana", "canal"])].copy()
                if not seg.empty:
                    chosen_campaign = st.selectbox("Campaña para segmentar", sorted(seg.campaign_date.unique()), format_func=lambda d: pd.Timestamp(d).strftime("%B %Y").capitalize(), key="campaign_segment_date")
                    seg = seg[seg.campaign_date.eq(chosen_campaign)]
                    for seg_type, title in [("banda_riesgo_originacion", "Banda de originación"), ("tipo_pagador_en_campana", "Tipo de pagador al asignar"), ("canal", "Canal de adquisición")]:
                        part = seg[seg.segment_type.eq(seg_type)]
                        if part.empty: continue
                        wide = part.pivot(index="segment", columns="group", values="itt_rate")
                        st.markdown(f"**{title}**")
                        if {"CONTROL", "TRATAMIENTO"}.issubset(wide.columns):
                            wide["Diferencia (pp) T - C"] = (wide["TRATAMIENTO"] - wide["CONTROL"]) * 100
                        for group_col in [c for c in ["CONTROL", "TRATAMIENTO"] if c in wide.columns]:
                            wide[group_col] = wide[group_col].map(fmt_pct)
                        if "Diferencia (pp) T - C" in wide.columns:
                            wide["Diferencia (pp) T - C"] = wide["Diferencia (pp) T - C"].map(lambda v: "—" if pd.isna(v) else f"{v:+.1f}".replace(".", ","))
                        st.dataframe(wide.reset_index().rename(columns={"segment": "Segmento"}), width="stretch", hide_index=True)
            st.caption("Diferencias observadas; revisar balance inicial e incertidumbre antes de atribuir causalidad.")
    with tab_limits:
        section("Evolución de límites y exposición", "Límite activo, saldo, utilización y cuentas con aumento registrado por corte.")
        lm = limit_metrics(cuts)
        lm = lm[lm.fecha_corte.isin(selected_dates)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=lm.fecha_corte, y=lm.active_limit, mode="lines+markers", name="Límite activo", line={"color": C["navy"], "width": 2.5}))
        fig.add_trace(go.Scatter(x=lm.fecha_corte, y=lm.balance, mode="lines+markers", name="Saldo activo", line={"color": C["blue2"], "width": 2.5}))
        fig.update_yaxes(tickprefix="Q ", tickformat=",.0f")
        chart(fig, "limits_exposure", 320)
        fig = go.Figure(go.Bar(x=lm.fecha_corte, y=lm.accounts_increased, marker_color=C["blue"], text=lm.accounts_increased.map(fmt_num), textposition="outside"))
        fig.update_layout(yaxis_title="Cuentas con aumento")
        chart(fig, "limits_increase_count", 280)
        increase_table = lm[["fecha_corte", "accounts_increased", "increase_amount", "avg_limit", "utilization"]].copy()
        increase_table["increase_amount"] = increase_table.increase_amount.map(fmt_money)
        increase_table["avg_limit"] = increase_table.avg_limit.map(fmt_money)
        increase_table["utilization"] = increase_table.utilization.map(fmt_pct)
        st.dataframe(increase_table.rename(columns={"fecha_corte": "Corte", "accounts_increased": "Cuentas con aumento", "increase_amount": "Incremento de límite", "avg_limit": "Límite promedio", "utilization": "Utilización"}), width="stretch", hide_index=True)
        section("Mora por utilización", "Mora 30+ / saldo activo.")
        a = active.copy(); a["utilization"] = a.saldo_corte / a.limite.replace(0, np.nan)
        a["util_band"] = pd.cut(a.utilization, [-np.inf, .25, .5, .75, 1, np.inf], labels=["≤25%", "26–50%", "51–75%", "76–100%", ">100%"])
        a["bad_balance"] = np.where(a.dias_mora.ge(30), a.saldo_corte, 0)
        util = a.groupby("util_band", observed=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), bad=("bad_balance", "sum")).reset_index()
        util["rate"] = util.bad / util.balance.replace(0, np.nan)
        fig = go.Figure(go.Bar(x=util.util_band.astype(str), y=util.rate, marker_color=C["navy"], text=util.rate.map(fmt_pct), textposition="outside", customdata=util[["accounts", "balance"]], hovertemplate="Utilización: %{x}<br>Mora 30+: %{y:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Saldo: Q %{customdata[1]:,.0f}<extra></extra>"))
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        chart(fig, "limits_util_risk", 320)
        section("Riesgo por tamaño de línea", "Cuentas, utilización y mora 30+ por límite vigente.")
        a["limit_band"] = pd.cut(a.limite, [-np.inf, 3000, 5000, 7500, np.inf], labels=["Hasta Q3 mil", "Q3–5 mil", "Q5–7,5 mil", "Más de Q7,5 mil"])
        limit_band = a.groupby("limit_band", observed=False).agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"), limit=("limite", "sum"), bad_balance=("bad_balance", "sum"), bad_accounts=("dias_mora", lambda x: int((x >= 30).sum()))).reset_index()
        limit_band["utilization"] = limit_band.balance / limit_band.limit.replace(0, np.nan)
        limit_band["bad_rate"] = limit_band.bad_balance / limit_band.balance.replace(0, np.nan)
        fig = go.Figure(go.Bar(x=limit_band.limit_band.astype(str), y=limit_band.bad_rate, marker_color=C["blue"], text=limit_band.bad_rate.map(fmt_pct), textposition="outside", customdata=limit_band[["accounts", "utilization", "balance"]], hovertemplate="Límite: %{x}<br>Mora 30+ sobre saldo: %{y:.1%}<br>Cuentas: %{customdata[0]:,.0f}<br>Utilización: %{customdata[1]:.1%}<br>Saldo: Q %{customdata[2]:,.0f}<extra></extra>"))
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        chart(fig, "limits_size_risk", 320)
        limit_show = limit_band.copy(); limit_show["Utilización"] = limit_show.utilization.map(fmt_pct); limit_show["Mora 30+ / saldo"] = limit_show.bad_rate.map(fmt_pct); limit_show["Saldo"] = limit_show.balance.map(fmt_money)
        st.dataframe(limit_show[["limit_band", "accounts", "Saldo", "Utilización", "Mora 30+ / saldo"]].rename(columns={"limit_band": "Banda de límite", "accounts": "Cuentas"}), width="stretch", hide_index=True)


def unit_page(accounts, cuts, campaigns, selected_date, selected_dates):
    page_header("Movimientos financieros registrados", "Intereses, cargos por mora, pagos y castigos registrados en los cortes disponibles.", accounts, cuts, campaigns, selected_date, "economia")
    rows = []
    for date, g in cuts.groupby("fecha_corte"):
        active = active_only(g)
        charged = g[g.estado.astype(str).str.upper().eq("CASTIGADA")]
        interest = g.intereses_mes.sum(); fees = g.cargos_mora_mes.sum(); payments = g.pago_realizado.sum()
        rows.append({"fecha_corte": date, "interest": interest, "fees": fees, "payments": payments,
                     "recorded_total": interest + fees, "active_accounts": active.id_cuenta.nunique(),
                     "per_active": safe_div(interest + fees, active.id_cuenta.nunique()),
                     "chargeoff": charged.saldo_castigado.sum()})
    rev = pd.DataFrame(rows).sort_values("fecha_corte")
    rev = rev[rev.fecha_corte.isin(selected_dates)]
    cur = rev[rev.fecha_corte.eq(selected_date)]
    if cur.empty: st.info("No hay datos para el corte seleccionado."); return
    c = cur.iloc[-1]
    metric_row([("Intereses registrados", fmt_money(c.interest), None), ("Cargos por mora", fmt_money(c.fees), None),
                ("Pagos recibidos", fmt_money(c.payments), None), ("Castigos", fmt_money(c.chargeoff), None),
                ("Intereses + cargos", fmt_money(c.recorded_total), None)], cols=5)
    left, right = st.columns(2)
    with left:
        section("Intereses y cargos registrados", "Suma de intereses_mes y cargos_mora_mes en cada corte.")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=rev.fecha_corte, y=rev.interest, name="Intereses", marker_color=C["navy"]))
        fig.add_trace(go.Bar(x=rev.fecha_corte, y=rev.fees, name="Cargos por mora", marker_color=C["amber"]))
        fig.update_layout(barmode="stack"); fig.update_yaxes(tickprefix="Q ", tickformat=",.0f")
        chart(fig, "unit_recorded_flows", 340)
    with right:
        section("Importe registrado por cuenta activa", "Intereses más cargos por mora dividido entre cuentas activas del corte.")
        fig = go.Figure(go.Scatter(x=rev.fecha_corte, y=rev.per_active, mode="lines+markers", line={"color": C["blue"], "width": 2.8}))
        fig.update_yaxes(tickprefix="Q ", tickformat=",.0f")
        chart(fig, "unit_per_account", 340)
    section("Pagos recibidos", "Suma de pago_realizado en cada corte; representa pagos registrados entre el corte anterior y el actual.")
    fig = go.Figure(go.Bar(x=rev.fecha_corte, y=rev.payments, marker_color=C["teal"], text=rev.payments.map(fmt_money), textposition="outside"))
    fig.update_xaxes(tickformat="%b %Y"); fig.update_yaxes(tickprefix="Q ", tickformat=",.0f", rangemode="tozero")
    chart(fig, "unit_payments_received", 300)
    section("Castigos contables", "Saldo castigado reportado en cada corte. Los datos disponibles abarcan mayo–octubre de 2026.")
    fig = go.Figure(go.Bar(x=rev.fecha_corte, y=rev.chargeoff, marker_color=C["slate"], text=[fmt_money(x) if x else "—" for x in rev.chargeoff], textposition="outside"))
    fig.update_xaxes(tickformat="%b %Y"); fig.update_yaxes(tickprefix="Q ", tickformat=",.0f", rangemode="tozero")
    chart(fig, "unit_chargeoffs", 320)
    st.caption("Los intereses y cargos son importes registrados, no ingreso neto. Pago_realizado registra pagos recibidos entre cortes. No hay datos de interchange, fondeo, recompensas, costos operativos ni recuperaciones. El castigo es una salida contable de cartera, no un ingreso.")


def render_app():
    st.set_page_config(page_title="Vana | Riesgo de crédito", page_icon="V", layout="wide", initial_sidebar_state="expanded")
    inject_css()
    accounts, cuts, campaigns = load_data(_source_fingerprint())
    view_state = {}
    page_titles = ["Key Metrics", "Portafolio", "Riesgo de crédito", "Cobranza y límites", "Economía del portafolio"]

    def page_runner(title):
        def _run():
            fa = view_state.get("accounts", accounts)
            fc = view_state.get("cuts", cuts)
            fm = view_state.get("campaigns", campaigns)
            dates = view_state.get("selected_dates", sorted(cuts.fecha_corte.dropna().unique()))
            if not dates or fa.empty or fc.empty:
                st.info("No hay cuentas para la combinación de filtros seleccionada. Ajusta los filtros de cartera.")
                return
            selected_date = max(dates)
            if title == "Key Metrics":
                executive_page(fa, fc, fm, selected_date, dates)
            elif title == "Portafolio":
                portfolio_page(fa, fc, fm, selected_date, dates)
            elif title == "Riesgo de crédito":
                risk_page(fa, fc, fm, selected_date, dates)
            elif title == "Cobranza y límites":
                collections_page(fa, fc, fm, selected_date, dates)
            else:
                unit_page(fa, fc, fm, selected_date, dates)
        return _run

    page_objects = {
        title: st.Page(page_runner(title), title=title, url_path=re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"))
        for title in page_titles
    }
    selected_page = st.navigation(
        {"ANÁLISIS DE CARTERA": [page_objects[t] for t in page_titles[:3]],
         "GESTIÓN DE CARTERA": [page_objects[t] for t in page_titles[3:]]},
        position="hidden",
    )
    _, fa, fc, dates, fm = sidebar(accounts, cuts, campaigns, page_objects, selected_page.title)
    view_state.update({"accounts": fa, "cuts": fc, "campaigns": fm, "selected_dates": dates})
    selected_page.run()
