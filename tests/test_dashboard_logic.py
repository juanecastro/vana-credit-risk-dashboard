import numpy as np
import pandas as pd
import pytest

from credit_card.src.ui.dashboard import (
    active_only,
    behavior_transitions,
    delinquency_bucket,
    fmt_money,
    fmt_num,
    fmt_pct,
    label,
    monthly_portfolio,
    partner_metrics,
    safe_div,
)


# ---------------------------------------------------------------------
# Formatting and utility functions
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1234.56, "1.234,56"),
        (1000, "1.000"),
        (0, "0"),
        (np.nan, "—"),
    ],
)
def test_fmt_num(value, expected):
    assert fmt_num(value, 2 if value == 1234.56 else 0) == expected


def test_fmt_money():
    assert fmt_money(1234.56, 2) == "Q 1.234,56"
    assert fmt_money(np.nan) == "—"


def test_fmt_pct():
    assert fmt_pct(0.2009, 2) == "20,09%"
    assert fmt_pct(np.nan) == "—"


def test_label_handles_known_unknown_and_missing_values():
    assert label("PAGA_MINIMO") == "Paga el mínimo"
    assert label("AL23") == "AL23"
    assert label("UNKNOWN_VALUE") == "Unknown Value"
    assert label(np.nan) == "Sin dato"


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (10, 2, 5),
        (10, 0, np.nan),
        (10, None, np.nan),
        (10, np.nan, np.nan),
    ],
)
def test_safe_div(numerator, denominator, expected):
    result = safe_div(numerator, denominator)

    if np.isnan(expected):
        assert np.isnan(result)
    else:
        assert result == expected


# ---------------------------------------------------------------------
# Account classification
# ---------------------------------------------------------------------

def test_active_only_is_case_insensitive_and_does_not_modify_input():
    data = pd.DataFrame(
        {
            "id_cuenta": ["A", "B", "C"],
            "estado": ["ACTIVA", "activa", "CASTIGADA"],
        }
    )

    result = active_only(data)

    assert result.id_cuenta.tolist() == ["A", "B"]
    assert len(data) == 3


def test_delinquency_bucket_classifies_boundaries():
    data = pd.DataFrame(
        {
            "estado": [
                "ACTIVA", "ACTIVA", "ACTIVA", "ACTIVA",
                "ACTIVA", "ACTIVA", "ACTIVA", "ACTIVA",
                "CASTIGADA",
            ],
            "dias_mora": [0, 1, 29, 30, 60, 90, 120, 150, 180],
        }
    )

    result = delinquency_bucket(data).tolist()

    assert result == [
        "Al día",
        "1–29",
        "1–29",
        "30–59",
        "60–89",
        "90–119",
        "120–149",
        "150–179",
        "Castigada",
    ]


# ---------------------------------------------------------------------
# Portfolio aggregation
# ---------------------------------------------------------------------

def test_monthly_portfolio_separates_active_and_charged_off_accounts():
    date = pd.Timestamp("2026-10-31")

    cuts = pd.DataFrame(
        {
            "fecha_corte": [date, date, date],
            "id_cuenta": ["A", "B", "C"],
            "estado": ["ACTIVA", "ACTIVA", "CASTIGADA"],
            "saldo_corte": [100.0, 50.0, 0.0],
            "saldo_castigado": [0.0, 0.0, 40.0],
            "limite": [200.0, 100.0, 0.0],
            "dias_mora": [0, 30, 180],
        }
    )

    accounts = pd.DataFrame(
        {
            "id_cuenta": ["A", "B", "C"],
            "fecha_apertura": pd.to_datetime(
                ["2026-10-01", "2026-09-01", "2026-10-10"]
            ),
        }
    )

    result = monthly_portfolio(cuts, accounts).iloc[0]

    assert result.active_accounts == 2
    assert result.active_balance == 150.0
    assert result.active_limit == 300.0
    assert result.utilization == pytest.approx(0.5)
    assert result.dpd30_balance == 50.0
    assert result.dpd30_balance_rate == pytest.approx(1 / 3)
    assert result.dpd30_accounts == 1
    assert result.chargeoff_accounts == 1
    assert result.chargeoff_balance == 40.0
    assert result.new_accounts == 2
    assert result.cumulative_chargeoff == 40.0


def test_partner_metrics_calculates_partner_delinquency_separately():
    data = pd.DataFrame(
        {
            "id_cuenta": ["A", "B", "C", "D"],
            "estado": ["ACTIVA", "ACTIVA", "ACTIVA", "CASTIGADA"],
            "canal": [
                "ALIADO_COMERCIAL",
                "ALIADO_COMERCIAL",
                "ALIADO_COMERCIAL",
                "ALIADO_COMERCIAL",
            ],
            "id_aliado": ["AL01", "AL01", "AL02", "AL02"],
            "dias_mora": [30, 0, 60, 180],
            "saldo_corte": [100.0, 100.0, 300.0, 0.0],
        }
    )

    result = partner_metrics(data).set_index("id_aliado")

    assert set(result.index) == {"AL01", "AL02"}
    assert result.loc["AL01", "accounts"] == 2
    assert result.loc["AL01", "balance"] == 200.0
    assert result.loc["AL01", "bad_balance"] == 100.0
    assert result.loc["AL01", "balance_rate"] == pytest.approx(0.5)
    assert result.loc["AL01", "account_rate"] == pytest.approx(0.5)
    assert result.loc["AL02", "bad_balance"] == 300.0


def test_partner_metrics_returns_empty_result_without_eligible_partners():
    data = pd.DataFrame(
        {
            "id_cuenta": ["A"],
            "estado": ["ACTIVA"],
            "canal": ["DIGITAL_ABIERTO"],
            "id_aliado": [None],
            "dias_mora": [0],
            "saldo_corte": [100.0],
        }
    )

    assert partner_metrics(data).empty


# ---------------------------------------------------------------------
# Behaviour transitions
# ---------------------------------------------------------------------

def test_behavior_transitions_keeps_only_consecutive_months():
    cuts = pd.DataFrame(
        {
            "id_cuenta": ["A", "A", "A", "B", "B"],
            "fecha_corte": pd.to_datetime(
                [
                    "2026-08-31",
                    "2026-09-30",
                    "2026-11-30",
                    "2026-08-31",
                    "2026-10-31",
                ]
            ),
            "estado": ["ACTIVA", "ACTIVA", "ACTIVA", "ACTIVA", "ACTIVA"],
            "dias_mora": [0, 30, 0, 0, 0],
            "tipo_pagador": ["TOTALERO", "PAGA_MINIMO", "TOTALERO", "NO_PAGA", "TOTALERO"],
            "score_comportamiento": [700, 650, 720, 500, 600],
        }
    )

    result = behavior_transitions(cuts)

    assert len(result) == 1
    row = result.iloc[0]

    assert row.id_cuenta == "A"
    assert row.fecha_corte == pd.Timestamp("2026-08-31")
    assert row.next_date == pd.Timestamp("2026-09-30")
    assert bool(row.next_30) is True
    assert bool(row.next_1plus) is True
