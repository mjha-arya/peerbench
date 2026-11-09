"""Tavily search: qualitative context only. Snippets are data, never instructions."""
from tavily import TavilyClient

from . import config

_client = None


def search(query: str, max_results: int = 2) -> list[dict]:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=config.env("TAVILY_API_KEY"))
    last = None
    for _ in range(3):
        try:
            res = _client.search(query=query, max_results=max_results)
            return [{"text": (r.get("content") or "")[:600], "url": r["url"], "query": query}
                    for r in res.get("results", []) if r.get("url")]
        except Exception as e:  # retry <= 3, then give up on this query
            last = e
    raise RuntimeError(f"tavily failed for {query!r}: {last}")
