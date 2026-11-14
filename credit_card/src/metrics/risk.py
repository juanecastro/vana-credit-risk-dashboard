import pandas as pd

from credit_card.src.metrics.common import (
    RISK_BAND_ORDER,
    add_consecutive_next_observation,
    prepare_risk_data,
    safe_divide,
)


def calculate_segment_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    segment_column: str,
    cut_date=None,
) -> pd.DataFrame:
    df = prepare_risk_data(accounts, cuts)
    if segment_column not in df.columns:
        raise ValueError(f"Unknown segment column: {segment_column}")
    if cut_date is None:
        cut_date = df["fecha_corte"].max()
    else:
        cut_date = pd.Timestamp(cut_date)

    snapshot = df[df["fecha_corte"] == cut_date]
    results = []
    for segment, group in snapshot.groupby(segment_column, dropna=False):
        active = group[group["estado"] == "ACTIVA"]
        charged_off = group[group["estado"] == "CASTIGADA"]
        delinquent = active[active["dias_mora"] >= 30]
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        results.append({
            segment_column: segment,
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "average_balance": safe_divide(active_balance, active_accounts),
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
            "charged_off_accounts_at_cut": charged_off["id_cuenta"].nunique(),
            "charged_off_balance_at_cut": charged_off["saldo_castigado"].sum(),
        })
    return pd.DataFrame(results).sort_values("dpd_30_rate", ascending=False).reset_index(drop=True)


def calculate_origination_score_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    mob: int = 2,
) -> pd.DataFrame:
    df = prepare_risk_data(accounts, cuts)
    df = df[df["meses_en_libros"] == mob].copy()
    df["banda_riesgo_originacion"] = pd.Categorical(
        df["banda_riesgo_originacion"],
        categories=RISK_BAND_ORDER,
        ordered=True,
    )
    results = []
    for band, group in df.groupby("banda_riesgo_originacion", observed=True):
        active = group[group["estado"] == "ACTIVA"]
        charged_off = group[group["estado"] == "CASTIGADA"]
        delinquent = active[active["dias_mora"] >= 30]
        observed_accounts = group["id_cuenta"].nunique()
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        deteriorated_ids = set(delinquent["id_cuenta"]) | set(charged_off["id_cuenta"])
        results.append({
            "risk_band": band,
            "observed_accounts": observed_accounts,
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
            "chargeoff_accounts_at_mob": charged_off["id_cuenta"].nunique(),
            "deteriorated_accounts_at_mob": len(deteriorated_ids),
            "deterioration_rate_at_mob": safe_divide(len(deteriorated_ids), observed_accounts),
        })
    return pd.DataFrame(results)


def calculate_score_channel_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    mob: int = 2,
) -> pd.DataFrame:
    df = prepare_risk_data(accounts, cuts)
    df = df[df["meses_en_libros"] == mob].copy()
    df["banda_riesgo_originacion"] = pd.Categorical(
        df["banda_riesgo_originacion"],
        categories=RISK_BAND_ORDER,
        ordered=True,
    )
    results = []
    for (channel, band), group in df.groupby(
        ["canal", "banda_riesgo_originacion"], observed=True
    ):
        active = group[group["estado"] == "ACTIVA"]
        delinquent = active[active["dias_mora"] >= 30]
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        results.append({
            "canal": channel,
            "banda_riesgo": band,
            "observed_accounts": group["id_cuenta"].nunique(),
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
        })
    return pd.DataFrame(results).sort_values(["canal", "banda_riesgo"]).reset_index(drop=True)


def calculate_behavior_score_performance(cuts: pd.DataFrame) -> pd.DataFrame:
    df = add_consecutive_next_observation(cuts)
    eligible = df[
        (df["estado"] == "ACTIVA")
        & (df["dias_mora"] < 30)
        & df["has_consecutive_next_month"]
    ].copy()
    eligible["next_deteriorated"] = (
        (eligible["next_dias_mora"] >= 30)
        | (eligible["next_estado"] == "CASTIGADA")
    )
    eligible["behavior_score_band"] = pd.cut(
        eligible["score_comportamiento"],
        bins=[0, 300, 600, 800, 950, 999],
        labels=["1-300", "301-600", "601-800", "801-950", "951-999"],
        include_lowest=True,
    )
    results = []
    for band, group in eligible.groupby("behavior_score_band", observed=True):
        results.append({
            "behavior_score_band": band,
            "eligible_observations": len(group),
            "unique_accounts": group["id_cuenta"].nunique(),
            "new_deterioration_events": int(group["next_deteriorated"].sum()),
            "next_month_deterioration_rate": group["next_deteriorated"].mean(),
        })
    return pd.DataFrame(results).sort_values("behavior_score_band").reset_index(drop=True)


def calculate_cutoff_policy_comparison(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    mob: int = 2,
) -> pd.DataFrame:
    df = prepare_risk_data(accounts, cuts)
    df["policy_period"] = df["fecha_apertura"].apply(
        lambda date: "Antes de junio 2026" if date < pd.Timestamp("2026-06-01") else "Desde junio 2026"
    )
    observed = df[df["meses_en_libros"] == mob].copy()
    results = []
    for period, group in observed.groupby("policy_period"):
        active = group[group["estado"] == "ACTIVA"]
        charged_off = group[group["estado"] == "CASTIGADA"]
        delinquent = active[active["dias_mora"] >= 30]
        observed_accounts = group["id_cuenta"].nunique()
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        low_score_accounts = group.loc[
            group["banda_riesgo_originacion"] == "E", "id_cuenta"
        ].nunique()
        total_originations = accounts.loc[
            accounts["fecha_apertura"].apply(
                lambda date: date < pd.Timestamp("2026-06-01")
                if period == "Antes de junio 2026"
                else date >= pd.Timestamp("2026-06-01")
            ), "id_cuenta"
        ].nunique()
        results.append({
            "policy_period": period,
            "total_originated_accounts": total_originations,
            "observed_accounts_at_mob": observed_accounts,
            "observed_vintages": ", ".join(sorted(group["cosecha"].dropna().unique())),
            "active_accounts": active_accounts,
            "score_560_599_accounts": low_score_accounts,
            "share_score_560_599": safe_divide(low_score_accounts, observed_accounts),
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
            "chargeoff_accounts_at_mob": charged_off["id_cuenta"].nunique(),
            "channel_mix_accounts": group["canal"].value_counts(normalize=True).to_dict(),
        })
    return pd.DataFrame(results).sort_values("policy_period").reset_index(drop=True)


def calculate_partner_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    mob: int = 2,
) -> pd.DataFrame:
    df = prepare_risk_data(accounts, cuts)
    df = df[(df["meses_en_libros"] == mob) & (df["canal"] == "ALIADO_COMERCIAL")]
    results = []
    for partner, group in df.groupby("id_aliado", dropna=False):
        active = group[group["estado"] == "ACTIVA"]
        delinquent = active[active["dias_mora"] >= 30]
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        results.append({
            "partner": partner,
            "observed_accounts": group["id_cuenta"].nunique(),
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
            "average_origination_score": group["score_originacion"].mean(),
            "share_no_bureau": (group["historial_buro"] == "SIN_HISTORIAL").mean(),
            "share_informal_employment": (group["tipo_empleo"] == "INFORMAL").mean(),
        })
    return pd.DataFrame(results).sort_values("dpd_30_rate", ascending=False).reset_index(drop=True)
