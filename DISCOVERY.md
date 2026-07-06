# Discovery - be-eli-mcp (Belgium, Moniteur Belge / Belgisch Staatsblad)

Date: 2026-07-06. Decision: **BUILD** (clean keyless, HTML-structured, ELI-coordinate source,
reachable and parseable this session).

## Context

Belgium's official gazette is `ejustice.just.fgov.be`, run by the Federal Public Service Justice.
The EU eur-lex ELI register documents Belgium's ELI grammar; a third-party catalog
(`worldwidelaw/legal-sources`, `sources/BE/moniteurbelge/config.yaml`) additionally names the
endpoint shapes and a `cgi/article_body.pl` fallback. Both were used as leads, not trusted
blindly - every claim below was independently re-probed live against production.

## Source (probed live, not trusted from docs)

- **Host:** `https://www.ejustice.just.fgov.be`. Keyless, no auth headers required.
- **ELI grammar (confirmed live):**
  `GET /eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel` returns the consolidated act as HTML, `200 OK`.
  `type` confirmed working for `loi` and `arrete`; `decret`, `ordonnance`, `constitution` follow
  the same catalog-documented grammar but were not each individually re-fetched this session.
  `numac` is Belgium's own legislative numbering system (10-digit, e.g. `2020040054`).
- **`/moniteur` variant** (original as-published text, same ELI path with `/moniteur` suffix
  instead of `/justel`): returned **404** for the one NUMAC tested (`2020040054`), even though the
  year-listing page links to it. Not every NUMAC has a `/moniteur` manifestation reachable this
  way, or the suffix requires different handling than assumed. **Not wired into a tool** in
  v0.1.0 - flagged as an open point in CONSTITUTION.md rather than forced.
- **No free-text search API.** The only browse mechanism found is the year-listing page
  `/eli/{type}/{year}`, which lists all NUMACs published that year for that type (242 entries for
  `loi`/2020) - this is a listing, not a keyword search. Same "get-by-coordinate" shape as
  `ie-eli-mcp` (Ireland: year+number+type) and `lu-eli-mcp` (Luxembourg: ELI-native, no SPARQL).
- **Not-found is HTTP 200, not 404.** A constructed ELI path with a non-existent NUMAC
  (`.../9999999999/justel`) returns HTTP 200 with a byte-for-byte-similar-length empty shell page
  (same `list`/`links` div skeleton, no `list-item--title` or `Texte` block). Confirmed by
  comparing response length (7974 bytes for both a real `arrete` fixture and the fake-NUMAC
  fixture) and by absence of the title/text markup. `citations.has_content()` is the guard.
- **Response format: structured HTML, not prose-scrape.** The `/justel` page carries stable,
  class-named blocks: `<p class="list-item--title">` (title), a `plain-text` block with
  labelled `<strong>Source:</strong>` / `<strong>Publication:</strong>` /
  `<strong>Numero:</strong>` / `<strong>Entree en vigueur:</strong>` fields, a `<h2 id="text">`
  ("Texte"/"Tekst") section containing `Art. N.` anchors, and a `Liens` section with the
  canonical ELI URL and a PDF link. This is regex-parseable in the same spirit as `ie-eli-mcp`'s
  ISB header-block extraction - not fragile prose-scraping.
- **Trilingual.** `/cgi_loi/article.pl?language={fr|nl|de}&numac_search={numac}&caller=eli`
  toggles the language of the same NUMAC (confirmed: FR and NL both returned 200 with correctly
  translated `Texte`/`Tekst` sections for the test act). German was not individually re-fetched
  but follows the same URL pattern per the site's own language nav links. **Gotcha found during
  smoke testing:** the `cn_search=...&view_numac={numac}fr` parameter combination (copied from
  the site's own FR nav link, which happened to still resolve to full FR content) does **not**
  reliably serve full content for other languages - for NL it returned a short stub/redirect page
  with no title/text blocks. Switching to `numac_search={numac}` (dropping `cn_search`/
  `view_numac` entirely) reliably returns the full structured page for all three languages.
- **worldwidelaw's `cgi/article_body.pl` fallback claim: not independently confirmed.** The
  `/justel` page already provides complete full text + metadata, so this session did not need
  the CGI fallback and did not verify it live. Documented as an open point, not asserted as
  working.
- **Licence:** the worldwidelaw catalog and data.gov.be convention describe Belgian federal
  Moniteur Belge data as CC0. This session did not locate and parse an explicit licence grant on
  ejustice.just.fgov.be itself (the footer links only to a generic "Conditions d'utilisation"
  PDF). Treated as inherited-and-plausible, not independently verified - see CONSTITUTION Art. 1.

## Citation contract mapping

| Field | Source |
| --- | --- |
| `eli_uri` | constructed from caller-supplied coordinates, confirmed against real page content before being returned (never fabricated for a not-found coordinate) |
| `human_readable_citation` | the parsed Belgian title ("D MOIS YYYY. - Loi/Arrete ..."), French by LDH convention; NL/DE available via `language` param |
| `source_url` | the same ELI URL (no separate human portal exists) |

## Build

`audit.py` + `cache.py` reused verbatim (env `BE_ELI_*`, log `be-eli-mcp.jsonl`). New for BE:
`client.py` (keyless GET of `/justel` pages, language-toggle CGI endpoint, year-listing pages),
`citations.py` (regex extraction of the class-named HTML blocks + content-based not-found
detection + year-listing entry parsing), `models.py`, `server.py` (3 tools: `be_get_act`,
`be_get_text`, `be_list_year`; `ToolError` {invalid_arg / not_found / upstream_error}). Tests:
offline drift + offline fixture parse (3 live-captured HTML fixtures in `tests/fixtures/`) + live
smoke. The factory holds: infrastructure reused, only the source adapter is new.
