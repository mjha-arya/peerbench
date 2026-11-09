"""check_numbers: every number in the LLM's prose must trace to a computed fact or a snippet.
Pit Box pattern: invented figures are caught in code, not by asking the model nicely."""
import re

NUM = re.compile(
    r"(?<![A-Za-z0-9.\-])(\$)?(-)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s*(%|pp\b|percentage points?\b|points?\b|billion\b|million\b|thousand\b|bn\b|B\b|M\b|K\b))?",
    re.I,
)
URL = re.compile(r"https?://\S+")
TAG = re.compile(r"\[S\d+\]")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SCALE = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}


def extract(text: str) -> list[tuple[str, float, str]]:
    """Return (kind, value, raw) for each number: kind is pct | money | plain."""
    text = DATE.sub(" ", TAG.sub(" ", URL.sub(" ", text)))
    out = []
    for m in NUM.finditer(text):
        dollar, neg, whole, frac, unit = m.groups()
        val = float(whole.replace(",", "") + (frac or ""))
        if neg:
            val = -val
        u = (unit or "").lower()
        if u in ("%", "pp") or u.startswith("percentage") or u.startswith("point"):
            out.append(("pct", val, m.group(0)))
        elif u in SCALE:
            out.append(("money", val * SCALE[u], m.group(0)))
        elif dollar:
            out.append(("money", val, m.group(0)))
        else:
            out.append(("plain", val, m.group(0)))
    return out


def allowed_sets(facts_pct: list[float], facts_money: list[float], years: list[int], snippet_texts: list[str]):
    pcts = {round(abs(x), 1) for x in facts_pct if x is not None}
    money = {abs(x) for x in facts_money if x is not None}
    plain = set(years)
    for t in snippet_texts:
        for kind, v, _ in extract(t):
            {"pct": pcts, "money": money}.get(kind, plain).add(round(abs(v), 1) if kind == "pct" else abs(v))
    return pcts, money, plain


def _near_pct(v, pcts):
    return any(abs(abs(v) - a) <= 0.15 for a in pcts)


def _near_money(v, money):
    return any(a and abs(abs(v) - a) / a <= 0.015 for a in money)


def check_numbers(prose: str, pcts: set, money: set, plain: set) -> list[str]:
    """Return the raw strings of numbers that trace to nothing."""
    bad = []
    for kind, v, raw in extract(prose):
        if kind == "pct" and _near_pct(v, pcts):
            continue
        if kind == "money" and _near_money(v, money):
            continue
        if kind == "plain":
            if v in plain or (float(v).is_integer() and 0 <= v <= 10):
                continue
            if _near_pct(v, pcts) or _near_money(v, money) or abs(v) in plain:
                continue
        bad.append(raw.strip())
    return bad
