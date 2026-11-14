import pandas as pd

from credit_card.src.metrics.common import add_mora_bucket, add_previous_observation, safe_divide


def calculate_payer_mix(cuts: pd.DataFrame, cut_date=None) -> pd.DataFrame:
    if cut_date is None:
        cut_date = cuts["fecha_corte"].max()
    else:
        cut_date = pd.Timestamp(cut_date)
    snapshot = cuts[(cuts["fecha_corte"] == cut_date) & (cuts["estado"] == "ACTIVA")]
    total_accounts = snapshot["id_cuenta"].nunique()
    total_balance = snapshot["saldo_corte"].sum()
    result = (
        snapshot.groupby("tipo_pagador", dropna=False)
        .agg(accounts=("id_cuenta", "nunique"), balance=("saldo_corte", "sum"))
        .reset_index()
    )
    result["account_share"] = result["accounts"] / total_accounts if total_accounts else 0
    result["balance_share"] = result["balance"] / total_balance if total_balance else 0
    result.insert(0, "fecha_corte", cut_date)
    return result


def calculate_payer_transitions(cuts: pd.DataFrame) -> pd.DataFrame:
    df = add_mora_bucket(cuts)
    df = df.sort_values(["id_cuenta", "fecha_corte"]).copy()
    grouped = df.groupby("id_cuenta", sort=False)
    df["next_fecha_corte"] = grouped["fecha_corte"].shift(-1)
    df["next_dias_mora"] = grouped["dias_mora"].shift(-1)
    df["next_estado"] = grouped["estado"].shift(-1)
    df["next_tipo_pagador"] = grouped["tipo_pagador"].shift(-1)
    expected = df["fecha_corte"] + pd.offsets.MonthEnd(1)
    pairs = df[df["next_fecha_corte"].eq(expected) & (df["estado"] == "ACTIVA")].copy()
    pairs["next_outcome"] = pairs["next_tipo_pagador"].where(
        pairs["next_estado"] == "ACTIVA", "CASTIGADA"
    )
    result = (
        pairs.groupby(["tipo_pagador", "next_outcome"], dropna=False)
        .agg(observations=("id_cuenta", "size"), accounts=("id_cuenta", "nunique"))
        .reset_index()
    )
    result["transition_rate"] = result["observations"] / result.groupby("tipo_pagador")["observations"].transform("sum")
    return result.sort_values(["tipo_pagador", "next_outcome"]).reset_index(drop=True)


def calculate_payer_early_warning(cuts: pd.DataFrame) -> pd.DataFrame:
    df = cuts.sort_values(["id_cuenta", "fecha_corte"]).copy()
    grouped = df.groupby("id_cuenta", sort=False)
    df["next_fecha_corte"] = grouped["fecha_corte"].shift(-1)
    df["next_dias_mora"] = grouped["dias_mora"].shift(-1)
    df["next_estado"] = grouped["estado"].shift(-1)
    expected = df["fecha_corte"] + pd.offsets.MonthEnd(1)
    eligible = df[
        (df["estado"] == "ACTIVA")
        & (df["dias_mora"] == 0)
        & df["next_fecha_corte"].eq(expected)
    ].copy()
    eligible["next_1_plus"] = (
        (eligible["next_dias_mora"] >= 1)
        | (eligible["next_estado"] == "CASTIGADA")
    )
    eligible["next_30_plus_or_chargeoff"] = (
        (eligible["next_dias_mora"] >= 30)
        | (eligible["next_estado"] == "CASTIGADA")
    )
    return (
        eligible.groupby("tipo_pagador")
        .agg(
            eligible_observations=("id_cuenta", "size"),
            unique_accounts=("id_cuenta", "nunique"),
            next_1_plus_events=("next_1_plus", "sum"),
            next_1_plus_rate=("next_1_plus", "mean"),
            next_30_plus_events=("next_30_plus_or_chargeoff", "sum"),
            next_30_plus_rate=("next_30_plus_or_chargeoff", "mean"),
        )
        .reset_index()
    )


def calculate_delinquency_roll_rates(cuts: pd.DataFrame) -> pd.DataFrame:
    df = add_mora_bucket(cuts)
    df = add_previous_observation(df)
    pairs = df[df["has_consecutive_prev_month"]].copy()
    pairs = pairs.rename(columns={"mora_bucket": "current_bucket"})
    pairs["previous_bucket"] = pairs["prev_altura_mora"].map({
        "0. Al dia": "AL_DIA",
        "1. 1-29": "MORA_1_29",
        "2. 30-59": "MORA_30_59",
        "3. 60-89": "MORA_60_89",
        "4. 90-119": "MORA_90_119",
        "5. 120-149": "MORA_120_149",
        "6. 150-179": "MORA_150_179",
        "7. 180+ castigo": "CASTIGADA",
    })
    result = (
        pairs.groupby(["previous_bucket", "current_bucket"], observed=True)
        .agg(transitions=("id_cuenta", "size"), accounts=("id_cuenta", "nunique"))
        .reset_index()
    )
    result["transition_rate"] = result["transitions"] / result.groupby("previous_bucket")["transitions"].transform("sum")
    return result.sort_values(["previous_bucket", "current_bucket"]).reset_index(drop=True)


def calculate_collections_contact_metrics(cuts: pd.DataFrame) -> pd.DataFrame:
    df = add_previous_observation(cuts)
    eligible = df[
        df["has_consecutive_prev_month"]
        & (df["prev_dias_mora"] > 0)
        & df["gestion_cobranza_mes"].isin(["CONTACTADO", "NO_CONTACTADO"])
    ].copy()
    previous_bucket_map = {
        "0. Al dia": "AL_DIA",
        "1. 1-29": "MORA_1_29",
        "2. 30-59": "MORA_30_59",
        "3. 60-89": "MORA_60_89",
        "4. 90-119": "MORA_90_119",
        "5. 120-149": "MORA_120_149",
        "6. 150-179": "MORA_150_179",
        "7. 180+ castigo": "CASTIGADA",
    }
    eligible["previous_mora_bucket"] = eligible["prev_altura_mora"].map(previous_bucket_map)
    eligible["outcome"] = "MORA_1_29"
    eligible.loc[(eligible["estado"] == "CASTIGADA"), "outcome"] = "CASTIGADA"
    eligible.loc[(eligible["estado"] == "ACTIVA") & (eligible["dias_mora"] == 0), "outcome"] = "AL_DIA"
    eligible.loc[(eligible["estado"] == "ACTIVA") & (eligible["dias_mora"] >= 30), "outcome"] = "MORA_30_PLUS"
    eligible.loc[(eligible["estado"] == "ACTIVA") & eligible["dias_mora"].between(1, 29), "outcome"] = "MORA_1_29"
    result = (
        eligible.groupby(["gestion_cobranza_mes", "previous_mora_bucket", "outcome"])
        .agg(observations=("id_cuenta", "size"), accounts=("id_cuenta", "nunique"))
        .reset_index()
    )
    result["outcome_rate"] = result["observations"] / result.groupby(
        ["gestion_cobranza_mes", "previous_mora_bucket"]
    )["observations"].transform("sum")
    return result.sort_values(
        ["previous_mora_bucket", "gestion_cobranza_mes", "outcome"]
    ).reset_index(drop=True)
