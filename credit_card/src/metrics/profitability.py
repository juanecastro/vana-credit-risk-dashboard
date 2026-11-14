import pandas as pd

from credit_card.src.metrics.common import safe_divide


def calculate_revenue_proxy(cuts: pd.DataFrame) -> pd.DataFrame:
    results = []
    for cut_date, group in cuts.groupby("fecha_corte", sort=True):
        active = group[group["estado"] == "ACTIVA"]
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        interest_revenue = group["intereses_mes"].sum()
        late_fee_revenue = group["cargos_mora_mes"].sum()
        results.append({
            "fecha_corte": cut_date,
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "interest_revenue_proxy": interest_revenue,
            "late_fee_revenue_proxy": late_fee_revenue,
            "total_revenue_proxy": interest_revenue + late_fee_revenue,
            "revenue_proxy_per_active_account": safe_divide(interest_revenue + late_fee_revenue, active_accounts),
            "interest_proxy_to_active_balance": safe_divide(interest_revenue, active_balance),
            "chargeoff_balance_flow": group.loc[group["estado"] == "CASTIGADA", "saldo_castigado"].sum(),
        })
    return pd.DataFrame(results)


def calculate_observed_credit_costs(cuts: pd.DataFrame) -> pd.DataFrame:
    chargeoffs = cuts[cuts["estado"] == "CASTIGADA"].copy()
    monthly = (
        chargeoffs.groupby("fecha_corte")
        .agg(
            chargeoff_accounts=("id_cuenta", "nunique"),
            chargeoff_balance=("saldo_castigado", "sum"),
        )
    )
    result = pd.DataFrame(index=sorted(cuts["fecha_corte"].unique()))
    result.index.name = "fecha_corte"
    result = result.join(monthly).fillna(0).reset_index()
    result["cumulative_chargeoff_accounts"] = result["chargeoff_accounts"].cumsum()
    result["cumulative_chargeoff_balance"] = result["chargeoff_balance"].cumsum()
    return result
