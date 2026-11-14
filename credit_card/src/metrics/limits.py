import pandas as pd

from credit_card.src.metrics.common import safe_divide


def prepare_campaign_data(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    campaigns: pd.DataFrame,
) -> pd.DataFrame:
    account_columns = [
        "id_cuenta", "canal", "id_aliado", "score_originacion",
        "banda_riesgo_originacion", "tipo_empleo", "historial_buro",
        "ingreso_mensual_declarado", "region",
    ]
    campaign_data = campaigns.merge(
        accounts[account_columns],
        on="id_cuenta",
        how="left",
        validate="one_to_one",
    )
    baseline = cuts[[
        "id_cuenta", "fecha_corte", "saldo_corte", "limite",
        "score_comportamiento", "dias_mora", "estado", "compras_mes",
    ]].copy()
    campaign_data = campaign_data.merge(
        baseline,
        left_on=["id_cuenta", "corte_campana"],
        right_on=["id_cuenta", "fecha_corte"],
        how="left",
        validate="one_to_one",
    )
    campaign_data["baseline_utilization"] = (
        campaign_data["saldo_corte"] / campaign_data["limite_anterior"].replace(0, pd.NA)
    )
    return campaign_data


def calculate_campaign_baseline(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    campaigns: pd.DataFrame,
) -> pd.DataFrame:
    df = prepare_campaign_data(accounts, cuts, campaigns)
    results = []
    for (campaign_date, group_name), group in df.groupby(["corte_campana", "grupo"]):
        results.append({
            "campaign_date": campaign_date,
            "group": group_name,
            "assigned_accounts": group["id_cuenta"].nunique(),
            "average_origination_score": group["score_originacion"].mean(),
            "average_behavior_score": group["score_comportamiento"].mean(),
            "average_limit_before": group["limite_anterior"].mean(),
            "average_limit_after": group["limite_despues"].mean(),
            "average_balance_at_campaign": group["saldo_corte"].mean(),
            "average_utilization_at_campaign": group["baseline_utilization"].mean(),
            "share_560_599": (group["banda_riesgo_originacion"] == "E").mean(),
            "share_no_bureau": (group["historial_buro"] == "SIN_HISTORIAL").mean(),
            "share_informal_employment": (group["tipo_empleo"] == "INFORMAL").mean(),
            "channel_mix": group["canal"].value_counts(normalize=True).to_dict(),
            "payer_mix": group["tipo_pagador_en_campana"].value_counts(normalize=True).to_dict(),
            "baseline_dpd_1_29_accounts": (group["altura_mora_en_campana"] == "1. 1-29").sum(),
        })
    return pd.DataFrame(results).sort_values(["campaign_date", "group"]).reset_index(drop=True)


def calculate_campaign_followup(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    campaigns: pd.DataFrame,
) -> pd.DataFrame:
    max_cut = cuts["fecha_corte"].max()
    results = []
    for campaign_date, campaign_group in campaigns.groupby("corte_campana"):
        assigned = campaign_group[["id_cuenta", "grupo"]].drop_duplicates()
        for horizon in range(1, 13):
            target_date = campaign_date + pd.offsets.MonthEnd(horizon)
            if target_date > max_cut:
                break
            snapshot = cuts[cuts["fecha_corte"] == target_date].copy()
            prior_history = cuts[
                (cuts["fecha_corte"] > campaign_date)
                & (cuts["fecha_corte"] <= target_date)
            ]
            ever_30_ids = set(prior_history.loc[
                (prior_history["dias_mora"] >= 30) | (prior_history["estado"] == "CASTIGADA"),
                "id_cuenta",
            ])
            chargeoff_history = prior_history[prior_history["estado"] == "CASTIGADA"]
            for group_name, group in assigned.groupby("grupo"):
                ids = set(group["id_cuenta"])
                active = snapshot[(snapshot["id_cuenta"].isin(ids)) & (snapshot["estado"] == "ACTIVA")]
                charged_off_ids = ids & set(chargeoff_history["id_cuenta"])
                delinquent = active[active["dias_mora"] >= 30]
                cumulative_deteriorated = (ids & ever_30_ids)
                active_accounts = active["id_cuenta"].nunique()
                active_balance = active["saldo_corte"].sum()
                results.append({
                    "campaign_date": campaign_date,
                    "horizon_months": horizon,
                    "target_date": target_date,
                    "group": group_name,
                    "assigned_accounts": len(ids),
                    "observed_active_accounts": active_accounts,
                    "chargeoff_accounts_cumulative": len(charged_off_ids),
                    "dpd_30_accounts_at_horizon": delinquent["id_cuenta"].nunique(),
                    "dpd_30_account_rate_active": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
                    "dpd_30_balance_at_horizon": delinquent["saldo_corte"].sum(),
                    "dpd_30_balance_rate_active": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
                    "cumulative_ever_30_or_chargeoff_accounts": len(cumulative_deteriorated),
                    "cumulative_ever_30_or_chargeoff_rate_itt": safe_divide(len(cumulative_deteriorated), len(ids)),
                    "average_active_balance": safe_divide(active_balance, active_accounts),
                    "average_active_limit": safe_divide(active["limite"].sum(), active_accounts),
                    "average_monthly_purchases": safe_divide(active["compras_mes"].sum(), active_accounts),
                })
    return pd.DataFrame(results).sort_values(
        ["campaign_date", "horizon_months", "group"]
    ).reset_index(drop=True)


def calculate_campaign_segment_followup(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    campaigns: pd.DataFrame,
    segment_column: str = "tipo_pagador_en_campana",
    horizon: int = 2,
) -> pd.DataFrame:
    allowed = {
        "tipo_pagador_en_campana", "altura_mora_en_campana",
        "canal", "banda_riesgo_originacion", "tipo_empleo", "historial_buro",
    }
    if segment_column not in allowed:
        raise ValueError(f"Unsupported campaign segment: {segment_column}")
    df = prepare_campaign_data(accounts, cuts, campaigns)
    results = []
    for campaign_date, campaign_group in df.groupby("corte_campana"):
        target_date = campaign_date + pd.offsets.MonthEnd(horizon)
        if target_date > cuts["fecha_corte"].max():
            continue
        snapshot = cuts[cuts["fecha_corte"] == target_date]
        prior_history = cuts[
            (cuts["fecha_corte"] > campaign_date)
            & (cuts["fecha_corte"] <= target_date)
        ]
        ever_30_ids = set(prior_history.loc[
            (prior_history["dias_mora"] >= 30) | (prior_history["estado"] == "CASTIGADA"),
            "id_cuenta",
        ])
        for (segment, group_name), group in campaign_group.groupby([segment_column, "grupo"], dropna=False):
            ids = set(group["id_cuenta"])
            active = snapshot[(snapshot["id_cuenta"].isin(ids)) & (snapshot["estado"] == "ACTIVA")]
            delinquent = active[active["dias_mora"] >= 30]
            results.append({
                "campaign_date": campaign_date,
                "target_date": target_date,
                "horizon_months": horizon,
                "segment": segment,
                "group": group_name,
                "assigned_accounts": len(ids),
                "observed_active_accounts": active["id_cuenta"].nunique(),
                "dpd_30_account_rate_active": safe_divide(delinquent["id_cuenta"].nunique(), active["id_cuenta"].nunique()),
                "cumulative_ever_30_or_chargeoff_rate_itt": safe_divide(len(ids & ever_30_ids), len(ids)),
            })
    return pd.DataFrame(results)
