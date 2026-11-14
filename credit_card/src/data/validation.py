
import pandas as pd


EXPECTED_COLUMNS = {
    "accounts": {
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
    },
    "cuts": {
        "id_cuenta",
        "fecha_corte",
        "meses_en_libros",
        "estado",
        "limite_anterior",
        "limite",
        "aumento_limite_en_corte",
        "saldo_corte_anterior",
        "pago_minimo_anterior",
        "pago_realizado",
        "tipo_pagador",
        "compras_mes",
        "intereses_mes",
        "cargos_mora_mes",
        "saldo_corte",
        "pago_minimo",
        "dias_mora",
        "altura_mora",
        "gestion_cobranza_mes",
        "score_comportamiento",
        "saldo_castigado",
    },
    "campaigns": {
        "id_cuenta",
        "corte_campana",
        "grupo",
        "limite_anterior",
        "limite_despues",
        "tipo_pagador_en_campana",
        "altura_mora_en_campana",
    },
}


def validate_data(data: dict) -> dict:
    errors = []
    warnings = []
    stats = {}

    required_datasets = {"accounts", "cuts", "campaigns"}
    missing_datasets = required_datasets - set(data.keys())

    if missing_datasets:
        errors.append(
            f"Missing datasets: {sorted(missing_datasets)}"
        )
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,
        }

    datasets = {
        "accounts": data["accounts"],
        "cuts": data["cuts"],
        "campaigns": data["campaigns"],
    }

    for name, df in datasets.items():
        stats[name] = {
            "rows": len(df),
            "columns": len(df.columns),
        }

        if df.empty:
            errors.append(f"{name}: dataset is empty")

        missing_columns = EXPECTED_COLUMNS[name] - set(df.columns)

        if missing_columns:
            errors.append(
                f"{name}: missing columns {sorted(missing_columns)}"
            )

    if errors:
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,
        }

    accounts = datasets["accounts"]
    cuts = datasets["cuts"]
    campaigns = datasets["campaigns"]

    for name, df in datasets.items():
        if df["id_cuenta"].isna().any():
            errors.append(f"{name}: null account IDs found")

    if accounts["id_cuenta"].duplicated().any():
        errors.append("accounts: duplicate account IDs found")

    if campaigns["id_cuenta"].duplicated().any():
        errors.append("campaigns: duplicate account IDs found")

    duplicate_cut_keys = cuts.duplicated(
        subset=["id_cuenta", "fecha_corte"]
    ).sum()

    if duplicate_cut_keys:
        errors.append(
            f"cuts: {duplicate_cut_keys} duplicate account/date combinations"
        )

    allowed_nulls = {
        "accounts": {"id_aliado"},
        "cuts": {"gestion_cobranza_mes"},
        "campaigns": set(),
    }

    for name, df in datasets.items():
        for column in df.columns:
            null_count = int(df[column].isna().sum())

            if null_count > 0 and column not in allowed_nulls[name]:
                warnings.append(
                    f"{name}.{column}: {null_count} missing values"
                )

    date_columns = {
        "accounts": ["fecha_apertura"],
        "cuts": ["fecha_corte"],
        "campaigns": ["corte_campana"],
    }

    for name, columns in date_columns.items():
        for column in columns:
            if not pd.api.types.is_datetime64_any_dtype(
                datasets[name][column]
            ):
                errors.append(
                    f"{name}.{column}: expected datetime type"
                )

    account_ids = set(accounts["id_cuenta"].dropna())

    orphan_cuts = int(
        (~cuts["id_cuenta"].isin(account_ids)).sum()
    )
    orphan_campaigns = int(
        (~campaigns["id_cuenta"].isin(account_ids)).sum()
    )

    if orphan_cuts:
        errors.append(
            f"cuts: {orphan_cuts} records reference unknown accounts"
        )

    if orphan_campaigns:
        errors.append(
            f"campaigns: {orphan_campaigns} records reference unknown accounts"
        )

    allowed_states = {"ACTIVA", "CASTIGADA"}
    unexpected_states = (
        set(cuts["estado"].dropna().unique()) - allowed_states
    )

    if unexpected_states:
        errors.append(
            f"cuts: unexpected states {unexpected_states}"
        )

    allowed_groups = {"TRATAMIENTO", "CONTROL"}
    unexpected_groups = (
        set(campaigns["grupo"].dropna().unique()) - allowed_groups
    )

    if unexpected_groups:
        errors.append(
            f"campaigns: unexpected groups {unexpected_groups}"
        )

    if (cuts["dias_mora"] < 0).any():
        errors.append("cuts: negative days past due found")

    if (cuts["meses_en_libros"] < 0).any():
        errors.append("cuts: negative months on book found")

    if (accounts["limite_inicial"] < 0).any():
        errors.append("accounts: negative initial limits found")

    if (cuts["limite"] < 0).any():
        errors.append("cuts: negative credit limits found")

    if (cuts["saldo_corte"] < 0).any():
        warnings.append("cuts: negative statement balances found")

    stats["accounts"]["unique_accounts"] = int(
        accounts["id_cuenta"].nunique()
    )

    stats["cuts"]["unique_accounts"] = int(
        cuts["id_cuenta"].nunique()
    )

    stats["cuts"]["reporting_dates"] = sorted(
        cuts["fecha_corte"]
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )

    stats["campaigns"]["treatment_accounts"] = int(
        (campaigns["grupo"] == "TRATAMIENTO").sum()
    )

    stats["campaigns"]["control_accounts"] = int(
        (campaigns["grupo"] == "CONTROL").sum()
    )

    stats["campaigns"]["treatment_share"] = round(
        (campaigns["grupo"] == "TRATAMIENTO").mean(),
        4,
    )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }


def assert_valid_data(data: dict) -> dict:
    report = validate_data(data)

    if not report["is_valid"]:
        error_message = "\n".join(report["errors"])
        raise ValueError(
            f"Data validation failed:\n{error_message}"
        )

    return report
