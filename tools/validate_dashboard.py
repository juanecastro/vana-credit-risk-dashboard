#!/usr/bin/env python3
"""Data-level smoke tests for the supplied synthetic Vana case dataset."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "credit_card" / "data" / "raw"


def main():
    accounts = pd.read_csv(RAW / "cuentas.csv")
    cuts = pd.read_csv(RAW / "cortes.csv")
    campaigns = pd.read_csv(RAW / "campanas_limite.csv", sep=";", encoding="utf-8-sig")
    cuts["fecha_corte"] = pd.to_datetime(cuts["fecha_corte"])
    campaigns["corte_campana"] = pd.to_datetime(campaigns["corte_campana"], dayfirst=True)

    assert accounts.id_cuenta.is_unique, "Cuentas must have one row per account"
    assert not cuts.duplicated(["id_cuenta", "fecha_corte"]).any(), "Duplicate account-cut rows found"
    assert set(cuts.id_cuenta).issubset(set(accounts.id_cuenta)), "Unmatched account IDs in cuts"
    assert len(accounts) == 11_400, f"Unexpected account count: {len(accounts)}"
    assert cuts.fecha_corte.min() == pd.Timestamp("2026-05-31")
    assert cuts.fecha_corte.max() == pd.Timestamp("2026-10-31")
    assert len(campaigns) == 1_001

    october = cuts[cuts.fecha_corte.eq(pd.Timestamp("2026-10-31"))].merge(accounts, on="id_cuenta")
    active = october[october.estado.eq("ACTIVA")]
    bad_balance = active.loc[active.dias_mora.ge(30), "saldo_corte"].sum()
    active_balance = active.saldo_corte.sum()
    rate = bad_balance / active_balance
    assert round(rate, 4) == 0.2009, f"Unexpected October 30+ balance rate: {rate}"

    partner = active[active.canal.eq("ALIADO_COMERCIAL")].copy()
    partner["bad_balance"] = partner.saldo_corte.where(partner.dias_mora.ge(30), 0)
    ranked = partner.groupby("id_aliado").agg(accounts=("id_cuenta", "nunique"), bad=("bad_balance", "sum"), balance=("saldo_corte", "sum"))
    ranked["rate"] = ranked.bad / ranked.balance
    top3 = ranked.sort_values("bad", ascending=False).head(3)
    assert list(top3.index) == ["AL23", "AL19", "AL07"], f"Unexpected top partners: {list(top3.index)}"

    print("PASS: account uniqueness, joins, monthly coverage, campaign records and October portfolio metrics")
    print(f"October active accounts: {active.id_cuenta.nunique():,}")
    print(f"October active balance: Q {active_balance:,.2f}")
    print(f"October 30+ balance rate: {rate:.2%}")
    print("Top three partners by delinquent balance:", ", ".join(top3.index))
    print(f"Top three share of total portfolio 30+ balance: {top3.bad.sum() / bad_balance:.2%}")


if __name__ == "__main__":
    main()
