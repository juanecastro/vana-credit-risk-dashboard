
from pathlib import Path

import pandas as pd

from credit_card.config.settings import (
    ACCOUNTS_FILE,
    CUTS_FILE,
    LIMIT_CAMPAIGNS_FILE,
)


def _check_file_exists(file_path: Path) -> None:
    """Check that a required dataset exists."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )


def _standardize_account_id(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize account IDs without changing their values."""

    df["id_cuenta"] = (
        df["id_cuenta"]
        .astype("string")
        .str.strip()
    )

    return df


def load_accounts(
    file_path: Path = ACCOUNTS_FILE,
) -> pd.DataFrame:
    """Load account origination information."""

    _check_file_exists(file_path)

    df = pd.read_csv(file_path)

    df = _standardize_account_id(df)

    df["fecha_apertura"] = pd.to_datetime(
        df["fecha_apertura"],
        format="%Y-%m-%d",
        errors="raise",
    )

    return df


def load_cuts(
    file_path: Path = CUTS_FILE,
) -> pd.DataFrame:
    """Load monthly account-level portfolio information."""

    _check_file_exists(file_path)

    df = pd.read_csv(file_path)

    df = _standardize_account_id(df)

    df["fecha_corte"] = pd.to_datetime(
        df["fecha_corte"],
        format="%Y-%m-%d",
        errors="raise",
    )

    return df


def load_limit_campaigns(
    file_path: Path = LIMIT_CAMPAIGNS_FILE,
) -> pd.DataFrame:
    """Load credit limit campaign information.

    Important:
    - This CSV uses semicolons as separators.
    - Campaign dates use DD/MM/YYYY format.
    """

    _check_file_exists(file_path)

    df = pd.read_csv(
        file_path,
        sep=";",
    )

    df = _standardize_account_id(df)

    df["corte_campana"] = pd.to_datetime(
        df["corte_campana"],
        format="%d/%m/%Y",
        errors="raise",
    )

    return df


def load_data() -> dict[str, pd.DataFrame]:
    """Load all three datasets.

    Returns a dictionary containing:

    - accounts: account origination information
    - cuts: monthly account-level information
    - campaigns: credit limit campaign information
    """

    data = {
        "accounts": load_accounts(),
        "cuts": load_cuts(),
        "campaigns": load_limit_campaigns(),
    }

    return data
