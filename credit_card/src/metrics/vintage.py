import pandas as pd

from credit_card.src.metrics.common import safe_divide


def prepare_vintage_data(accounts: pd.DataFrame, cuts: pd.DataFrame) -> pd.DataFrame:
    return cuts.merge(
        accounts[["id_cuenta", "fecha_apertura", "cosecha"]],
        on="id_cuenta",
        how="left",
        validate="many_to_one",
    )


def calculate_vintage_metrics(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
) -> pd.DataFrame:
    df = prepare_vintage_data(accounts, cuts)
    cohort_sizes = (
        accounts.groupby("cosecha")["id_cuenta"]
        .nunique()
        .rename("originated_accounts")
    )
    results = []

    for (vintage, mob), group in df.groupby(
        ["cosecha", "meses_en_libros"],
        sort=True,
    ):
        active = group[group["estado"] == "ACTIVA"]
        charged_off = group[group["estado"] == "CASTIGADA"]
        delinquent = active[active["dias_mora"] >= 30]
        active_accounts = active["id_cuenta"].nunique()
        active_balance = active["saldo_corte"].sum()
        originated = int(cohort_sizes.get(vintage, 0))
        results.append({
            "vintage": vintage,
            "mob": int(mob),
            "originated_accounts": originated,
            "observed_accounts": group["id_cuenta"].nunique(),
            "observation_coverage": safe_divide(group["id_cuenta"].nunique(), originated),
            "active_accounts": active_accounts,
            "active_balance": active_balance,
            "dpd_30_accounts": delinquent["id_cuenta"].nunique(),
            "dpd_30_account_rate": safe_divide(delinquent["id_cuenta"].nunique(), active_accounts),
            "dpd_30_balance": delinquent["saldo_corte"].sum(),
            "dpd_30_rate": safe_divide(delinquent["saldo_corte"].sum(), active_balance),
            "chargeoff_accounts_at_mob": charged_off["id_cuenta"].nunique(),
            "chargeoff_balance_at_mob": charged_off["saldo_castigado"].sum(),
        })

    return pd.DataFrame(results).sort_values(["vintage", "mob"]).reset_index(drop=True)


def calculate_vintage_curve(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
    metric: str = "dpd_30_rate",
) -> pd.DataFrame:
    metrics = calculate_vintage_metrics(accounts, cuts)
    if metric not in metrics.columns:
        raise ValueError(f"Unknown vintage metric: {metric}")
    return metrics.pivot(index="mob", columns="vintage", values=metric).sort_index()


def calculate_vintage_cumulative_outcomes(
    accounts: pd.DataFrame,
    cuts: pd.DataFrame,
) -> pd.DataFrame:
    df = prepare_vintage_data(accounts, cuts)
    results = []

    for cut_date in sorted(df["fecha_corte"].unique()):
        history = df[df["fecha_corte"] <= cut_date]
        ever_30_ids = set(
            history.loc[
                (history["estado"] == "ACTIVA") & (history["dias_mora"] >= 30),
                "id_cuenta",
            ].unique()
        )
        chargeoff_ids = set(
            history.loc[history["estado"] == "CASTIGADA", "id_cuenta"].unique()
        )
        deteriorated_ids = ever_30_ids | chargeoff_ids

        for vintage, group in accounts.groupby("cosecha"):
            ids = set(group["id_cuenta"])
            originated = len(ids)
            observed_ids = set(history.loc[history["cosecha"] == vintage, "id_cuenta"])
            results.append({
                "fecha_corte": cut_date,
                "vintage": vintage,
                "originated_accounts": originated,
                "observed_accounts_since_may": len(observed_ids),
                "ever_30_accounts_observed": len(ids & ever_30_ids),
                "cumulative_chargeoff_accounts": len(ids & chargeoff_ids),
                "ever_30_or_chargeoff_accounts_observed": len(ids & deteriorated_ids),
                "observed_deterioration_rate": safe_divide(len(ids & deteriorated_ids), originated),
            })

    return pd.DataFrame(results)
