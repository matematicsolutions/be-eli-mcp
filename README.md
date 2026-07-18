# be-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/be-eli-mcp -->

An MCP server for **Belgian legislation** via [Moniteur Belge / Belgisch Staatsblad]
(https://www.ejustice.just.fgov.be), the official gazette of the Belgian Federal Public Service
Justice. It fetches act metadata and full text by ELI coordinates, with verifiable citations.
Part of the **eu-legal-mcp** line of national legal connectors by [MateMatic](https://matematic.co).

Belgian legislation is addressed by ELI coordinates - `type` / `year` / `month` / `day` / `numac`
(the Belgian legislative numbering system) - at
`https://www.ejustice.just.fgov.be/eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel`. Every response
carries a native `eli_uri`, a `human_readable_citation` and a `source_url`.

> **Read-only.** The server only queries ejustice.just.fgov.be and writes a local audit log. It
> never modifies official text.

> **Belgium is trilingual** (French / Dutch / German). `human_readable_citation` defaults to the
> French form by LDH convention; use `be_get_text(language=...)` for Dutch (Belgisch Staatsblad)
> or German. See CONSTITUTION.md Art. 4 for the full caveat.

## Tools

| Tool | What it does |
| --- | --- |
| `be_get_act(doc_type, year, month, day, numac)` | Metadata for an act by its ELI coordinates. `doc_type` is one of `loi`, `decret`, `ordonnance`, `arrete`, `constitution`. Returns the native `eli_uri`, title, source authority, publication date, entry-into-force date, table of contents, and the citation contract. |
| `be_get_text(doc_type, year, month, day, numac, language="fr")` | The verbatim consolidated text ("Texte"/"Tekst" section) in `fr` (default), `nl` or `de`. |
| `be_list_year(doc_type, year)` | Browse a year's listing for one `doc_type`, to discover NUMAC coordinates. Titles in this listing are best-effort (may be `None`); call `be_get_act` for the authoritative title. |

There is **no free-text search**: ejustice.just.fgov.be exposes no keyword-search API. Discover
acts by ELI coordinates (from a citation you already hold) or by browsing `be_list_year`.

## Configuration

ejustice.just.fgov.be is keyless. Configuration is optional:

| Variable | Meaning |
| --- | --- |
| `BE_ELI_BASE_URL` | ejustice host (default `https://www.ejustice.just.fgov.be`). |
| `BE_ELI_CACHE_DIR` | Disk cache dir (default `~/.matematic/cache/be-eli`). |
| `BE_ELI_AUDIT_DIR` | Audit log dir (default `~/.matematic/audit`). |

Copy `.mcp.json.example` to your MCP client config.

## Install

```bash
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"   # Windows
# or: python -m pip install -e ".[dev]"                  # POSIX
```


### Windows 11 ze Smart App Control

Smart App Control blokuje niepodpisane pliki wykonywalne, a `uvx.exe`, `pip.exe`
i generowany przy instalacji `be-eli-mcp.exe` podpisane nie sa. `python.exe`
z python.org jest podpisany przez Python Software Foundation, wiec uruchomienie
przez modul omija blokade:

```bash
python -m pip install be-eli-mcp
python -m be_eli_mcp
```

```json
{ "mcpServers": { "be-eli-mcp": { "command": "python", "args": ["-m", "be_eli_mcp"] } } }
```

Nie wylaczaj Smart App Control, zeby to obejsc - wylaczenia nie da sie cofnac
bez ponownej instalacji systemu.

## Tests

```bash
pytest tests/test_instructions_drift.py tests/test_parse.py   # offline
pytest tests/test_smoke.py -v                                 # live, hits ejustice.just.fgov.be
```

## Licence

Apache-2.0. Moniteur Belge / Belgisch Staatsblad content is © the Belgian federal state; this
software only retrieves and cites it. See CONSTITUTION.md Art. 1 for a note on the licence status
of the source data (widely described as CC0 by third-party catalogs; not independently
re-verified against ejustice.just.fgov.be's own terms page in this project).
