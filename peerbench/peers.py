"""Peer resolution (name -> ticker) and peer financials from Yahoo Finance, cached 24 h."""
import json
import time

import yfinance as yf

from . import config
from .metrics import summarise


def _valid_equity(ticker: str) -> str | None:
    """Return the company's long name if `ticker` is a listed equity with income statements."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        if info.get("quoteType") != "EQUITY":
            return None
        if t.income_stmt is None or t.income_stmt.empty:
            return None
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return None


def search_ticker(name: str) -> str | None:
    """Code-first lookup: Yahoo search, primary listings (no exchange suffix) only."""
    try:
        quotes = yf.Search(name, max_results=5).quotes
    except Exception:
        return None
    for q in quotes:
        sym = q.get("symbol", "")
        if q.get("quoteType") == "EQUITY" and "." not in sym and "-" not in sym:
            return sym
    return None


def resolve(name: str, suggest) -> dict:
    """`suggest(name)` is the LLM fallback for misspellings; its answer is still validated in code."""
    for candidate, how in ((search_ticker(name), "yahoo-search"), (None, "llm")):
        if how == "llm":
            candidate = suggest(name)
        if candidate:
            long_name = _valid_equity(candidate)
            if long_name:
                return {"name": name, "ticker": candidate, "long_name": long_name, "how": how}
    return {"name": name, "ticker": None, "long_name": None, "how": "unresolved"}


def _row(stmt, col) -> dict:
    def get(*keys):
        for k in keys:
            if k in stmt.index and stmt.loc[k, col] == stmt.loc[k, col]:  # not NaN
                return float(stmt.loc[k, col])
        return None
    row = {"year": int(col.year), "revenue": get("Total Revenue", "Operating Revenue"),
           "gross_profit": get("Gross Profit"), "net_income": get("Net Income", "Net Income Common Stockholders"),
           "opex": get("Operating Expense")}
    if row["gross_profit"] is None:
        cost = get("Cost Of Revenue", "Reconciled Cost Of Revenue")
        if cost is not None and row["revenue"] is not None:
            row["gross_profit"] = row["revenue"] - cost
    return row


def fetch(ticker: str) -> dict:
    cache = config.CACHE / f"peer_{ticker}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < config.PEER_CACHE_HOURS * 3600:
        return json.loads(cache.read_text(encoding="utf-8"))
    stmt = yf.Ticker(ticker).income_stmt
    cols = [c for c in stmt.columns[:2]]
    rows = [r for r in (_row(stmt, c) for c in reversed(cols)) if r["revenue"] and r["net_income"] is not None]
    if not rows:
        raise ValueError(f"no usable income statement for {ticker}")
    m = summarise(rows)
    m["gross_profit"] = rows[-1].get("gross_profit")
    m["source"] = f"Yahoo Finance income statement, {ticker}, FY{m['year']}"
    m["url"] = f"https://finance.yahoo.com/quote/{ticker}/financials"
    cache.write_text(json.dumps(m), encoding="utf-8")
    return m
