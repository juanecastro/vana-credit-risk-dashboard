

# Vana Credit Risk Dashboard

An interactive credit portfolio monitoring dashboard built as part of a business case for a Lead Card role at Vana.

The goal was to turn a set of raw portfolio, account, monthly performance and credit-limit campaign files into a practical view of portfolio health — one that helps a credit and business team understand where risk is emerging, what is driving it, and which areas may need closer attention.

## What the dashboard covers

The dashboard is organised around five views:

- **Executive overview** — a concise snapshot of portfolio performance and how key indicators are changing over time.
- **Portfolio** — exposure, account growth, credit utilisation and portfolio composition.
- **Credit risk** — delinquency patterns across partners and channels, score performance, and vintage comparisons at the same months-on-books (MOB).
- **Collections and credit limits** — payer behaviour, collections-related views and the analysis of credit-limit campaigns.
- **Portfolio economics** — a view of portfolio economics using the information and revenue proxies available in the case data.

The analysis is designed to support questions such as: Is portfolio growth being accompanied by a deterioration in credit quality? Where is delinquency concentrated? Are newer vintages performing differently at comparable MOB? How do risk profiles vary across segments? And what does the available campaign evidence tell us about credit-limit increases?

## Approach

I built the dashboard around the decision questions in the case rather than simply reproducing the source files as charts.

The workflow combines account-level attributes with monthly account performance, applies consistent date and segment filters, and presents the resulting indicators across portfolio, risk and management views. The credit-risk analysis includes partner and channel comparisons, score ordering, payer segmentation and vintage analysis at comparable MOB.

For the credit-limit campaigns, the dashboard separates treatment and control outcomes and presents the observed difference in delinquency. These results should be interpreted in the context of the campaign assignment and observation window; they are not presented as proof of a causal impact without the appropriate validation.

An Excel export is also available so that users can take the filtered data away for further analysis. The workbook includes:

- `Parametros` — extraction timestamp, selected reporting dates, applied filters, record counts and a source-data fingerprint.
- `Datos` — monthly account observations enriched with account-level attributes.
- `Campanas` — credit-limit campaign assignment records for the included accounts.
- `Diccionario` — field descriptions supplied with the case data.

## Implementation

- **Python** for data preparation and analysis.
- **Pandas** for data manipulation, joins, filtering and metric calculations.
- **Streamlit** for the interactive dashboard and navigation.
- **XlsxWriter** for Excel generation.

The interface uses a multi-page layout with shared reporting-date and segment filters. The Excel export uses direct XlsxWriter row writing and lightweight formatting to reduce generation time.

## Run locally

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run credit_card/app.py
```

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Data and scope

The files included in this repository are synthetic data provided for the business case; they do not represent real Vana customers.

The dashboard is limited to the information available in the case materials. Where the data supports descriptive comparisons, the analysis is presented as descriptive rather than causal. Portfolio economics should likewise be read as an indicative view based on the available inputs, not as a complete profitability model.

---

*Built as a case-study deliverable to demonstrate structured credit-risk analysis, data handling and the translation of portfolio insights into a usable management tool.*

