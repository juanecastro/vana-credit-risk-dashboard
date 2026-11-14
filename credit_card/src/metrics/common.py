import pandas as pd

RISK_BAND_ORDER = ["E", "D", "C", "B", "A"]
PAYER_ORDER = [
    "TOTALERO",
    "ENTRE_MINIMO_Y_TOTAL",
    "PAGA_MINIMO",
    "MENOS_DEL_MINIMO",
    "NO_PAGA",
    "SIN_SALDO",
    "NUEVA_SIN_PAGO_EXIGIBLE",
]
MORA_BUCKET_ORDER = [
    "AL_DIA",
    "MORA_1_29",
    "MORA_30_59",
    "MORA_60_89",
    "MORA_90_119",
    "MORA_120_149",
    "MORA_150_179",
    "CASTIGADA",
]


def safe_divide(numerator, denominator):
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return 0.0
    return numerator / denominator


def prepare_risk_data(accounts: pd.DataFrame, cuts: pd.DataFrame) -> pd.DataFrame:
    account_columns = [
        "id_cuenta",
        "fecha_apertura",
        "cosecha",
        "canal",
        "id_aliado",
        "region",
        "edad",
        "tipo_empleo",
        "ingreso_mensual_declarado",
        "historial_buro",
        "score_originacion",
        "banda_riesgo_originacion",
        "limite_inicial",
    ]
    missing = [column for column in account_columns if column not in accounts.columns]
    if missing:
        raise ValueError(f"Missing account columns: {missing}")

    account_data = accounts[account_columns].copy()
    df = cuts.merge(
        account_data,
        on="id_cuenta",
        how="left",
        validate="many_to_one",
    )
    if df["fecha_apertura"].isna().any():
        raise ValueError("Some cut records do not match an account.")
    return df


def add_consecutive_next_observation(cuts: pd.DataFrame) -> pd.DataFrame:
    df = cuts.sort_values(["id_cuenta", "fecha_corte"]).copy()
    grouped = df.groupby("id_cuenta", sort=False)
    df["next_fecha_corte"] = grouped["fecha_corte"].shift(-1)
    df["next_dias_mora"] = grouped["dias_mora"].shift(-1)
    df["next_estado"] = grouped["estado"].shift(-1)
    df["next_tipo_pagador"] = grouped["tipo_pagador"].shift(-1)
    df["next_saldo_corte"] = grouped["saldo_corte"].shift(-1)
    expected_date = df["fecha_corte"] + pd.offsets.MonthEnd(1)
    df["has_consecutive_next_month"] = df["next_fecha_corte"].eq(expected_date)
    return df


def add_previous_observation(cuts: pd.DataFrame) -> pd.DataFrame:
    df = cuts.sort_values(["id_cuenta", "fecha_corte"]).copy()
    grouped = df.groupby("id_cuenta", sort=False)
    df["prev_fecha_corte"] = grouped["fecha_corte"].shift(1)
    df["prev_dias_mora"] = grouped["dias_mora"].shift(1)
    df["prev_estado"] = grouped["estado"].shift(1)
    df["prev_tipo_pagador"] = grouped["tipo_pagador"].shift(1)
    df["prev_saldo_corte"] = grouped["saldo_corte"].shift(1)
    df["prev_altura_mora"] = grouped["altura_mora"].shift(1)
    expected_date = df["prev_fecha_corte"] + pd.offsets.MonthEnd(1)
    df["has_consecutive_prev_month"] = df["fecha_corte"].eq(expected_date)
    return df


def classify_mora_bucket(row) -> str:
    if row["estado"] == "CASTIGADA":
        return "CASTIGADA"
    days = row["dias_mora"]
    if days <= 0:
        return "AL_DIA"
    if days <= 29:
        return "MORA_1_29"
    if days <= 59:
        return "MORA_30_59"
    if days <= 89:
        return "MORA_60_89"
    if days <= 119:
        return "MORA_90_119"
    if days <= 149:
        return "MORA_120_149"
    return "MORA_150_179"


def add_mora_bucket(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["mora_bucket"] = result.apply(classify_mora_bucket, axis=1)
    result["mora_bucket"] = pd.Categorical(
        result["mora_bucket"],
        categories=MORA_BUCKET_ORDER,
        ordered=True,
    )
    return result
