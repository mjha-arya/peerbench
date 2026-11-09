"""Deterministic finance maths. The LLM never calculates; everything numeric comes from here."""
import io

import pandas as pd

REQUIRED = ["year", "revenue", "cogs", "net_income"]
NUMERIC = ["revenue", "cogs", "opex", "net_income"]


class BadCSV(ValueError):
    pass


def load_csv(text: str) -> tuple[list[dict], list[str]]:
    """Return (rows sorted by year, ignored column names). Non-numeric columns are dropped,
    so free text in the CSV never reaches the model."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise BadCSV(f"CSV is missing column(s): {', '.join(missing)}")
    if df.empty:
        raise BadCSV("CSV has no data rows")
    keep = ["year"] + [c for c in NUMERIC if c in df.columns]
    ignored = [c for c in df.columns if c not in keep]
    for c in keep:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    bad = df[keep].isna().any(axis=1)
    if bad.any():
        raise BadCSV(f"Non-numeric value in row(s) {list(df.index[bad] + 2)}")
    df = df[keep].sort_values("year")
    rows = [{k: (int(v) if k == "year" else float(v)) for k, v in r.items()} for r in df.to_dict("records")]
    return rows, ignored


def pct(part: float, whole: float) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def summarise(rows: list[dict]) -> dict:
    """Metrics for the latest year plus growth. `rows` need revenue, cogs or gross_profit, net_income."""
    last = rows[-1]
    rev = last["revenue"]
    gross = last.get("gross_profit", rev - last.get("cogs", 0.0))
    out = {
        "year": last["year"],
        "revenue": rev,
        "net_income": last["net_income"],
        "gross_margin_pct": pct(gross, rev),
        "net_margin_pct": pct(last["net_income"], rev),
        "opex_ratio_pct": pct(last["opex"], rev) if last.get("opex") is not None else None,
        "revenue_growth_pct": None,
        "cagr_pct": None,
        "years": [r["year"] for r in rows],
    }
    if len(rows) >= 2 and rows[-2]["revenue"]:
        out["revenue_growth_pct"] = round((rev / rows[-2]["revenue"] - 1) * 100, 1)
    if len(rows) >= 3 and rows[0]["revenue"] > 0:
        n = rows[-1]["year"] - rows[0]["year"]
        if n > 0:
            out["cagr_pct"] = round(((rev / rows[0]["revenue"]) ** (1 / n) - 1) * 100, 1)
    return out


GAP_KEYS = ["revenue_growth_pct", "gross_margin_pct", "net_margin_pct", "opex_ratio_pct"]


def gaps(own: dict, peers: dict[str, dict]) -> dict[str, dict]:
    """Company minus peer, in percentage points, per metric."""
    out = {}
    for name, p in peers.items():
        out[name] = {k: round(own[k] - p[k], 1) for k in GAP_KEYS
                     if own.get(k) is not None and p.get(k) is not None}
    return out


def money(x: float | None) -> str:
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e9:
        return f"{sign}${x / 1e9:.2f}B"
    if x >= 1e6:
        return f"{sign}${x / 1e6:.1f}M"
    return f"{sign}${x:,.0f}"


def p(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1f}%"
