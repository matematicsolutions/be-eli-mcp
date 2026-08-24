"""FastMCP entry point - Belgian legislation (Moniteur Belge / Belgisch Staatsblad) tools.

Run:

    python -m be_eli_mcp.server

Configuration via env:

- ``BE_ELI_BASE_URL`` (default ``https://www.ejustice.just.fgov.be``)
- ``BE_ELI_CACHE_DIR`` (default ``~/.matematic/cache/be-eli``)
- ``BE_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
"""

from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import DOC_TYPES, parse_justel, parse_year_listing
from .client import DEFAULT_BASE_URL, EjusticeClient
from .models import Act, ActListing, DocType, Language, LawText
from .coverage import Coverage, build_coverage

INSTRUCTIONS = """\
This MCP server exposes Belgian legislation via Moniteur Belge / Belgisch Staatsblad (ejustice.just.fgov.be), Belgium's official gazette (Federal Public Service Justice), CC0-licensed and keyless. Legislation is addressed by ELI coordinates - type, year, month, day, NUMAC (Belgium's legislative numbering system) - at `/eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel`. Every response carries the citation contract: a native `eli_uri`, a `human_readable_citation` (French, by LDH convention - Belgium is trilingual FR/NL/DE) and a `source_url`.

## Call order

1. `be_get_act` - metadata for an act by its `doc_type` (`loi`, `decret`, `ordonnance`, `arrete`, `constitution`), `year`, `month`, `day` and `numac`. Returns the native `eli_uri`, title, source authority, publication date, entry-into-force date, table of contents, and the citation contract.
2. `be_get_text` - the verbatim consolidated text ("Texte"/"Tekst" section) of an act, in one `language` (default `fr`; `nl` and `de` also exist for most acts via the site's own language toggle).
3. `be_list_year` - browse a year's listing for one `doc_type`, to discover NUMAC coordinates when you do not already have one. Returns `ActListing` entries (NUMAC, publication date, source authority, and constructed ELI links) - titles in this listing are best-effort and may be `None`; call `be_get_act` for the authoritative title.

## Hard constraints

- **Do not answer past the edge of this corpus** - when a search comes back empty, or the question touches material this connector does not carry, call `be_coverage` and relay what it says is missing. Absence here is not absence in the law.
- **No free-text search** - ejustice.just.fgov.be exposes no keyword-search API. Discovery is by ELI coordinates (from a citation you already have) or by browsing `be_list_year` for a given type/year. Relay the `dataset_note`.
- **ELI is native** - the `eli_uri` is the real ejustice.just.fgov.be ELI URL for the requested coordinates; do not invent or alter it. A coordinate with no matching NUMAC returns HTTP 200 with an empty page (verified live) - this is surfaced as `not_found`, not silently returned as an empty `Act`.
- **Belgium is trilingual** - French is used as the primary `human_readable_citation` (LDH convention), but Dutch (Belgisch Staatsblad) and German texts exist for most acts; use `language` in `be_get_text` to fetch them.
- **No modification of official text** - text is returned verbatim from ejustice.just.fgov.be.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/be-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing, out of range, or not a recognized `doc_type`/`language`.
- `not_found` - no act exists for those coordinates (including the HTTP-200-empty-page case).
- `upstream_error` - an ejustice.just.fgov.be error (HTTP, timeout, malformed page). Retry once before surfacing.

## Response style

- Cite acts as `human_readable_citation` with the ELI: "Loi du 8 janvier 2020 ..., https://www.ejustice.just.fgov.be/eli/loi/2020/01/08/2020040054/justel".
- NEVER invent an ELI, a NUMAC, a title or a date - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for be-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="be-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("BE_ELI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No resource found on ejustice.just.fgov.be for those coordinates.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"ejustice.just.fgov.be error: {type(exc).__name__}: {exc}")
    return exc


def _validate_coords(doc_type: str, year: int, month: int, day: int, numac: str) -> None:
    if doc_type not in DOC_TYPES:
        raise ToolError("invalid_arg", f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}.")
    if not 1830 <= year <= 2100:
        raise ToolError("invalid_arg", f"year={year} is out of range (1830..2100).")
    if not 1 <= month <= 12:
        raise ToolError("invalid_arg", f"month={month} must be 1..12.")
    if not 1 <= day <= 31:
        raise ToolError("invalid_arg", f"day={day} must be 1..31.")
    if not numac or not numac.strip().isdigit():
        raise ToolError("invalid_arg", f"numac={numac!r} must be a non-empty numeric NUMAC.")


def _validate_language(language: str) -> None:
    if language not in ("fr", "nl", "de"):
        raise ToolError("invalid_arg", f"language must be one of 'fr'/'nl'/'de', got {language!r}.")


# ---------------------------------------------------------------------------
# be_get_act
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def be_get_act(doc_type: DocType, year: int, month: int, day: int, numac: str) -> Act:
    """Fetch metadata for a Belgian act by its ELI coordinates.

    Args:
        doc_type: one of ``loi``, ``decret``, ``ordonnance``, ``arrete``, ``constitution``.
        year: publication year, e.g. ``2020``.
        month: publication month, 1-12.
        day: publication day, 1-31.
        numac: the NUMAC identifier (Belgian legislative numbering system), e.g. ``2020040054``.

    Returns:
        ``Act`` with the native ``eli_uri``, title, source authority, dates, table of contents
        and the citation contract.
    """
    audit = _audit()
    _validate_coords(doc_type, year, month, day, numac)
    numac = numac.strip()
    input_hash = hash_input(
        {"doc_type": doc_type, "year": year, "month": month, "day": day, "numac": numac}
    )

    with timer() as t:
        try:
            async with EjusticeClient(base_url=_base_url()) as client:
                html, _url = await client.get_justel(doc_type, year, month, day, numac)
        except Exception as exc:
            audit.log(tool="be_get_act", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms or 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    parsed = parse_justel(html, doc_type, year, month, day, numac)
    if parsed is None:
        audit.log(tool="be_get_act", input_hash=input_hash, output_count_or_size=0,
                  duration_ms=t.duration_ms, status="error", error="not_found")
        raise ToolError(
            "not_found",
            f"No act found for doc_type={doc_type!r}, year={year}, month={month}, day={day}, "
            f"numac={numac!r} (ejustice.just.fgov.be returned an empty page for that coordinate).",
        )
    act = Act.model_validate(parsed)
    audit.log(tool="be_get_act", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return act


# ---------------------------------------------------------------------------
# be_get_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def be_get_text(
    doc_type: DocType, year: int, month: int, day: int, numac: str, language: Language = "fr"
) -> LawText:
    """Fetch the verbatim consolidated text of a Belgian act.

    Args:
        doc_type: one of ``loi``, ``decret``, ``ordonnance``, ``arrete``, ``constitution``.
        year: publication year.
        month: publication month, 1-12.
        day: publication day, 1-31.
        numac: the NUMAC identifier.
        language: ``fr`` (default), ``nl`` or ``de``.

    Returns:
        ``LawText`` with ``content`` (the "Texte"/"Tekst" section, HTML preserved for
        ``Art. N.`` structure) and the citation contract.
    """
    audit = _audit()
    _validate_coords(doc_type, year, month, day, numac)
    _validate_language(language)
    numac = numac.strip()
    input_hash = hash_input(
        {
            "doc_type": doc_type, "year": year, "month": month, "day": day,
            "numac": numac, "language": language,
        }
    )

    with timer() as t:
        try:
            async with EjusticeClient(base_url=_base_url()) as client:
                if language == "fr":
                    html, url = await client.get_justel(doc_type, year, month, day, numac)
                else:
                    html = await client.get_article_language(numac, language)
                    _, url = await client.get_justel(doc_type, year, month, day, numac)
        except Exception as exc:
            audit.log(tool="be_get_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms or 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    parsed = parse_justel(html, doc_type, year, month, day, numac)
    if parsed is None:
        audit.log(tool="be_get_text", input_hash=input_hash, output_count_or_size=0,
                  duration_ms=t.duration_ms, status="error", error="not_found")
        raise ToolError(
            "not_found",
            f"No text found for doc_type={doc_type!r}, year={year}, month={month}, day={day}, "
            f"numac={numac!r}, language={language!r}.",
        )

    from .citations import extract_text_section

    text_content = extract_text_section(html)
    if text_content is None:
        audit.log(tool="be_get_text", input_hash=input_hash, output_count_or_size=0,
                  duration_ms=t.duration_ms, status="error", error="not_found")
        raise ToolError(
            "not_found",
            f"Act found but no 'Texte'/'Tekst' section present for numac={numac!r} "
            f"(language={language!r}).",
        )

    result = LawText(
        numac=parsed.get("numac"),
        doc_type=doc_type,
        year=year,
        month=month,
        day=day,
        language=language,
        variant="justel",
        eli_uri=parsed.get("eli_uri"),
        human_readable_citation=parsed.get("human_readable_citation"),
        source_url=url,
        content=text_content,
        byte_size=len(text_content.encode("utf-8")),
    )
    audit.log(tool="be_get_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# be_list_year
@mcp.tool(annotations=READ_ONLY)
async def be_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the law "does not contain" something, and whenever
    a search comes back empty: the absence may be a gap in this connector rather than in the
    law. Every gap carries a fallback saying where to look instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    return build_coverage()


# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def be_list_year(doc_type: DocType, year: int) -> list[ActListing]:
    """Browse a year's listing of a Belgian legislation type, to discover NUMAC coordinates.

    Args:
        doc_type: one of ``loi``, ``decret``, ``ordonnance``, ``arrete``, ``constitution``.
        year: e.g. ``2020``.

    Returns:
        A list of ``ActListing`` (NUMAC, publication date, source authority, constructed ELI
        links). Titles are best-effort and may be ``None`` for some entries - call
        ``be_get_act`` for the authoritative title.
    """
    audit = _audit()
    if doc_type not in DOC_TYPES:
        raise ToolError("invalid_arg", f"doc_type must be one of {DOC_TYPES}, got {doc_type!r}.")
    if not 1830 <= year <= 2100:
        raise ToolError("invalid_arg", f"year={year} is out of range (1830..2100).")
    input_hash = hash_input({"doc_type": doc_type, "year": year})

    with timer() as t:
        try:
            async with EjusticeClient(base_url=_base_url()) as client:
                html, _url = await client.get_year_listing(doc_type, year)
        except Exception as exc:
            audit.log(tool="be_list_year", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms or 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    entries = parse_year_listing(html, doc_type, year)
    listings = [ActListing.model_validate(e) for e in entries]
    audit.log(tool="be_list_year", input_hash=input_hash, output_count_or_size=len(listings),
              duration_ms=t.duration_ms, status="ok")
    return listings


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
