import pandas as pd

from credit_card.src.metrics.common import safe_divide


def calculate_portfolio_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
) -> pd.DataFrame:
    account_dates = accounts[["id_cuenta", "fecha_apertura"]].copy()
    df = cuts.merge(
        account_dates,
        on="id_cuenta",
        how="left",
        validate="many_to_one",
    )
    if df["fecha_apertura"].isna().any():
        raise ValueError("Some cut records do not match an account.")

    results = []
    for cut_date, snapshot in df.groupby("fecha_corte", sort=True):
        active = snapshot[snapshot["estado"] == "ACTIVA"]
        charged_off = snapshot[snapshot["estado"] == "CASTIGADA"]
        delinquent_1_29 = active[active["dias_mora"].between(1, 29)]
        delinquent_30_plus = active[active["dias_mora"] >= 30]
        delinquent_1_plus = active[active["dias_mora"] >= 1]

        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        active_limit = active["limite"].sum()
        new_accounts = accounts[
            accounts["fecha_apertura"].dt.to_period("M")
            == cut_date.to_period("M")
        ]["id_cuenta"].nunique()
        cumulative_originations = accounts[
            accounts["fecha_apertura"] <= cut_date
        ]["id_cuenta"].nunique()
        prior_chargeoffs = df[
            (df["fecha_corte"] <= cut_date)
            & (df["estado"] == "CASTIGADA")
        ].drop_duplicates("id_cuenta")

        results.append({
            "fecha_corte": cut_date,
            "new_accounts": new_accounts,
            "cumulative_originations": cumulative_originations,
            "observed_accounts": snapshot["id_cuenta"].nunique(),
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "active_credit_limit": active_limit,
            "utilization_rate": safe_divide(active_balance, active_limit),
            "average_balance_per_active_account": safe_divide(active_balance, active_accounts),
            "average_limit_per_active_account": safe_divide(active_limit, active_accounts),
            "dpd_1_29_balance": delinquent_1_29["saldo_corte"].sum(),
            "dpd_1_29_balance_rate": safe_divide(delinquent_1_29["saldo_corte"].sum(), active_balance),
            "dpd_30_balance": delinquent_30_plus["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent_30_plus["saldo_corte"].sum(), active_balance),
            "dpd_30_accounts": delinquent_30_plus["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent_30_plus["id_cuenta"].nunique(), active_accounts),
            "dpd_1_plus_balance_rate": safe_divide(delinquent_1_plus["saldo_corte"].sum(), active_balance),
            "dpd_1_plus_account_rate": safe_divide(delinquent_1_plus["id_cuenta"].nunique(), active_accounts),
            "monthly_chargeoff_accounts": charged_off["id_cuenta"].nunique(),
            "monthly_chargeoff_balance": charged_off["saldo_castigado"].sum(),
            "cumulative_chargeoff_accounts": prior_chargeoffs["id_cuenta"].nunique(),
            "cumulative_chargeoff_balance": prior_chargeoffs["saldo_castigado"].sum(),
        })

    return pd.DataFrame(results).sort_values("fecha_corte").reset_index(drop=True)


def calculate_delinquency_distribution(
    cuts: pd.DataFrame,
    cut_date=None,
) -> pd.DataFrame:
    if cut_date is None:
        cut_date = cuts["fecha_corte"].max()
    else:
        cut_date = pd.Timestamp(cut_date)

    snapshot = cuts[
        (cuts["fecha_corte"] == cut_date)
        & (cuts["estado"] == "ACTIVA")
    ].copy()
    total_balance = snapshot["saldo_corte"].sum()
    total_accounts = snapshot["id_cuenta"].nunique()

    result = (
        snapshot.groupby("altura_mora", dropna=False)
        .agg(
            accounts=("id_cuenta", "nunique"),
            balance=("saldo_corte", "sum"),
        )
        .reset_index()
    )
    result["account_share"] = result["accounts"] / total_accounts if total_accounts else 0
    result["balance_share"] = result["balance"] / total_balance if total_balance else 0
    result.insert(0, "fecha_corte", cut_date)
    return result
