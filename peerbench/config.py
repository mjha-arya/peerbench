"""Paths, model choice and keys. Keys fall back to the Windows user environment
so a shell started before `setx` still sees them."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RUNS = DATA / "runs"
REPORTS = DATA / "reports"
CACHE = DATA / "cache"
CHECKPOINTS = DATA / "checkpoints.sqlite"
SOUL = ROOT / "soul.md"

MODEL = os.environ.get("PEERBENCH_MODEL", "gemini-3.8-flash")
# Tried in order when a model is over quota (429), overloaded (503) or retired (404). Free-tier quotas are per model.
FALLBACKS = os.environ.get("PEERBENCH_FALLBACKS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash,gemini-3.1-flash-lite").split(",")
MODELS = [MODEL] + [m.strip() for m in FALLBACKS if m.strip() and m.strip() != MODEL]
RPM = float(os.environ.get("PEERBENCH_RPM", "4"))  # Gemini free tier allows 5 requests/min per model
PEER_CACHE_HOURS = 24
PASS_SCORE = 8


def env(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


for _d in (RUNS, REPORTS, CACHE):
    _d.mkdir(parents=True, exist_ok=True)
