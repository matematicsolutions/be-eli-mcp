"""Async httpx client for Moniteur Belge / Belgisch Staatsblad (ejustice.just.fgov.be).

ejustice is keyless. Legal resources are addressed by ELI coordinates
(type/year/month/day/numac) and served as structured HTML (no JSON/XML API). We keep our own
backoff + disk cache. There is no free-text search endpoint - only a year-listing page per
legislation type, so discovery is by ELI coordinates plus optional year browsing, similar in
shape to ie-eli-mcp / lu-eli-mcp (get-by-coordinate, not full-text search).
"""

from __future__ import annotations

import anyio
import httpx

from .cache import HttpCache
from .citations import BASE, eli_uri

DEFAULT_BASE_URL = BASE
DEFAULT_TIMEOUT = httpx.Timeout(40.0, connect=10.0)
USER_AGENT = "be-eli-mcp/0.1.0 (+https://github.com/matematicsolutions/be-eli-mcp)"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class EjusticeClient:
    """Async client. Use as ``async with EjusticeClient() as c: ...``."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self) -> EjusticeClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _get(self, url: str, *, category: str) -> str:
        cache_key = f"GET {url}"
        cached = self._cache.get(cache_key)
        if cached is not None and isinstance(cached, str):
            return cached
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.get(url)
                resp.raise_for_status()
                text = resp.text
                self._cache.set(cache_key, text, ttl=HttpCache.ttl_for(category))
                return text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def get_justel(
        self, doc_type: str, year: int, month: int, day: int, numac: str
    ) -> tuple[str, str]:
        """Fetch the consolidated ``/justel`` HTML page. Returns (html, url)."""
        url = eli_uri(doc_type, year, month, day, numac, "justel")
        if self.base_url != DEFAULT_BASE_URL:
            url = url.replace(DEFAULT_BASE_URL, self.base_url)
        html = await self._get(url, category="act")
        return html, url

    async def get_article_language(self, numac: str, language: str) -> str:
        """Fetch a language variant of an act via the ``cgi_loi/article.pl`` endpoint.

        This is the endpoint the ejustice site itself links to for NL/FR/DE toggling from the
        ``/justel`` page (``lg_txt``/``language`` params), distinct from the worldwidelaw-noted
        ``article_body.pl`` fallback (which we did not find live-reachable with the same shape
        during discovery; see DISCOVERY.md). Uses ``numac_search`` (not ``cn_search`` +
        ``view_numac``) - the latter combination was found live to sometimes serve a stub
        redirect page rather than the full structured content.
        """
        lg_txt = {"fr": "f", "nl": "n", "de": "d"}.get(language, "f")
        url = (
            f"{self.base_url}/cgi_loi/article.pl?language={language}&lg_txt={lg_txt}"
            f"&type=&sort=&numac_search={numac}&caller=eli"
        )
        return await self._get(url, category="act")

    async def get_year_listing(self, doc_type: str, year: int) -> tuple[str, str]:
        """Fetch the year-listing page for a legislation type. Returns (html, url)."""
        url = f"{self.base_url}/eli/{doc_type}/{year}"
        html = await self._get(url, category="list")
        return html, url
