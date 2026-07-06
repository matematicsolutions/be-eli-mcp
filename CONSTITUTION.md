# Constitution of be-eli-mcp

Version: 0.1.0
Date: 2026-07-06
Licence: Apache-2.0

`be-eli-mcp` is an MCP server for Belgian legislation via Moniteur Belge / Belgisch Staatsblad
(`ejustice.just.fgov.be`), the official gazette of the Belgian Federal Public Service Justice. It
fetches act metadata and full text by ELI coordinates, with verifiable citations.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV).

---

## Art. 1. Public data only

ejustice.just.fgov.be is the official, public, keyless source of Belgian legislation. Content is
noted as CC Zero (CC0) by the third-party worldwidelaw/legal-sources catalog and by data.gov.be
convention for Belgian federal open data; **this project does not assert its own independent
confirmation of the CC0 licence text from ejustice.just.fgov.be itself** - the site's footer shows
only a generic "Conditions d'utilisation" PDF link, which this project has not parsed for a
licence grant. Treat the CC0 note as inherited-and-plausible, not verified-by-us. The server is
read-only against ejustice.just.fgov.be and sends nothing beyond the requested coordinates.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/be-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to write
= the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server talks
only to `www.ejustice.just.fgov.be` and the local filesystem. Authentication: none; own backoff +
cache.

## Art. 4. ELI citations and a human-readable citation are mandatory

Every response MUST carry three fields:

- `eli_uri`: the **native** ejustice.just.fgov.be ELI URL for the requested coordinates
  (`https://www.ejustice.just.fgov.be/eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel`). This is
  constructed from coordinates the caller supplied AND confirmed against the page's own content
  (title block present) before being returned - a coordinate with no matching NUMAC is surfaced
  as `not_found`, never as a fabricated or empty `Act`.
- `human_readable_citation`: built from the parsed Belgian title, which follows the "D MOIS
  YYYY. - Loi/Arrete/... " convention in the source itself. **Belgium is trilingual (French/Dutch/
  German)**: the title text ejustice returns depends on the language toggle used; this connector
  defaults to French for `human_readable_citation` by LDH (Le Droit Belge) convention, but this is
  an editorial default, not a claim that French is more "official" than Dutch or German - all
  three are co-official. Callers needing the Dutch (Belgisch Staatsblad) or German form should use
  `be_get_text(language="nl"|"de")`.
- `source_url`: the same ELI URL. Unlike Legilux (Luxembourg) or the Irish Statute Book,
  ejustice.just.fgov.be has no separate "human portal" distinct from the ELI page itself - the ELI
  URL IS the page a human would open.

---

## Open points

1. **No HTTP search** - ejustice.just.fgov.be exposes no keyword/full-text search API reachable
   without a browser session. Discovery is by ELI coordinates (from a citation you already hold)
   or by browsing `be_list_year` (a year-listing page per `doc_type`) for NUMAC discovery. This is
   the same "get-by-coordinate" shape as `ie-eli-mcp` and `lu-eli-mcp`.
2. **CGI fallback not used as primary path** - the worldwidelaw/legal-sources catalog names
   `/cgi/article_body.pl` as a fallback full-text endpoint. Live discovery in this session found
   the `/eli/.../justel` page itself already serves complete, structured full text with metadata,
   so the CGI fallback was not required and is not wired into `client.py`. The catalog's claim
   about `article_body.pl` was not independently re-verified; treat it as unconfirmed if a future
   maintainer needs it.
3. **Not-found is content-based, not status-based** - verified live: an ELI path with a
   non-existent NUMAC returns HTTP 200 with an empty shell page, not 404/410. `citations.py`
   detects this via `has_content()` (absence of the `list-item--title` block) rather than trusting
   the HTTP status code. Any future change to the site's error-page markup could silently break
   this detection; the offline fixture test (`test_parse.py::test_has_content_false_for_notfound_fixture`)
   guards it.
4. **Listing titles are best-effort** - `be_list_year` extracts titles from the year-listing page
   by proximity-matching a title-block regex to a date/source block; some entries (especially
   older administrative notices) have no title line in the listing and will return `title: null`.
   Callers wanting the authoritative title should call `be_get_act`.
5. **Consolidated ("justel") vs original ("moniteur") text** - this connector reads the
   `/justel` (consolidated) variant. The `/moniteur` (as-originally-published) variant exists as a
   separate ELI suffix but is not always present for every NUMAC (verified: some NUMACs 404 on
   `/moniteur`); it is not wired into a tool in this v0.1.0.

## Constitution evolution

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-07-06. Author: Wieslaw Mazur / MateMatic.
