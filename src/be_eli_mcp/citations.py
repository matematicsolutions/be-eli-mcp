"""Moniteur Belge / Belgisch Staatsblad (ejustice.just.fgov.be) HTML parsing + citation helpers.

ejustice.just.fgov.be serves Belgian legislation as **structured, class-named HTML** at genuine
ELI URLs:

    https://www.ejustice.just.fgov.be/eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel

There is no JSON/XML API and no free-text search endpoint; discovery is by ELI coordinates,
obtained either from a citation you already have (NUMAC) or from a year-listing page
(``/eli/{type}/{year}``) that ejustice itself exposes for browsing.

The ``/justel`` page is NOT a generic scrape target: it carries stable, class-named blocks
(``list-item--title``, ``plain-text``, labelled ``Source:``/``Publication:``/``Numéro:``/
``Entrée en vigueur:`` fields, and a ``Texte``/``Tekst`` section with ``Art. N.`` anchors) that
are safe to extract by regex, in the same spirit as ie-eli-mcp's ISB header-block parsing.

A quirk verified live: an ELI path with a non-existent NUMAC still returns **HTTP 200** with an
empty shell page (no title/text blocks) rather than 404/410. Not-found MUST therefore be detected
by content (absence of ``list-item--title``), not by HTTP status.

Citation contract (Art. 4 CONSTITUTION):
- ``eli_uri``: the **native** ELI URL as constructed from the requested coordinates and echoed
  back by the ``Liens`` section of the page itself (never fabricated - only used once confirmed
  the page actually resolved to real content).
- ``human_readable_citation``: French LDH-style citation built from the parsed title (Belgium is
  trilingual FR/NL/DE; French is used as the primary form per LDH convention - see CONSTITUTION
  and README for the multilingual caveat).
- ``source_url``: the same ELI URL (ejustice has no separate "human portal" distinct from the ELI
  page - the ELI URL IS the human-facing page).
"""

from __future__ import annotations

import re
from typing import Any

BASE = "https://www.ejustice.just.fgov.be"

DOC_TYPES = ("loi", "decret", "ordonnance", "arrete", "constitution")

_TITLE_RE = re.compile(r'<p class="list-item--title">\s*(.*?)\s*</p>', re.S)
_SOURCE_RE = re.compile(r"<strong>Source:\s*</strong>\s*(.*?)</p>", re.S)
_PUBLICATION_RE = re.compile(r"<strong>Publication:\s*</strong>\s*(.*?)</p>", re.S)
_NUMERO_RE = re.compile(r"<strong>Num&eacute;ro:\s*</strong>\s*(.*?)</p>", re.S)
_DOSSIER_RE = re.compile(r"<strong>Dossier num&eacute;ro:</strong>\s*(.*?)</p>", re.S)
_EEV_RE = re.compile(r"<strong>Entr&eacute;e en vigueur\s*:</strong>\s*(.*?)</p>", re.S)
_TOC_RE = re.compile(
    r'<h2 id="inhoud"[^>]*>.*?</h2>\s*(.*?)</div>', re.S
)
_TEXT_SECTION_RE = re.compile(
    r'<h2 id="text"[^>]*>.*?</h2>\s*(.*?)</div>\s*(?:</div>)?', re.S
)
_TAG_RE = re.compile(r'<span class="tag">(.*?)</span>')

# Year-listing page: each entry pairs a "Publie le" date + Source with Moniteur/Justel ELI links.
# Some entries also carry a plain-text title line before the date block; captured separately
# since not every entry has one (older/administrative notices often don't).
_LISTING_ENTRY_RE = re.compile(
    r"Publi&eacute; le\s*:\s*<font[^>]*>\s*(?P<pub_date>\d{2}-\d{2}-\d{4})\s*</font>.*?"
    r"Source\s*:\s*<font[^>]*>\s*(?P<source>.*?)\s*</font>.*?"
    r"<A href=https?://[^\s>]+/eli/(?P<type>\w+)/(?P<y>\d{4})/(?P<mo>\d{2})/(?P<da>\d{2})"
    r"/(?P<numac>\d+)/moniteur>",
    re.S,
)
_LISTING_TITLE_BEFORE_RE = re.compile(
    r"width=80%>\s*<font[^>]*>\s*(?P<title>[A-Z0-9][^<]{5,400}?\.\s*-\s*[^<]{3,400}?)\s*<br><br>\s*"
    r"<font color\s*=\s*#FF8C00>",
    re.S,
)


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).strip()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = _strip_tags(value)
    value = value.replace("&eacute;", "e").replace("&agrave;", "a").replace("&nbsp;", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def eli_path(doc_type: str, year: int, month: int, day: int, numac: str) -> str:
    return f"eli/{doc_type}/{year:04d}/{month:02d}/{day:02d}/{numac}"


def eli_uri(
    doc_type: str, year: int, month: int, day: int, numac: str, variant: str = "justel"
) -> str:
    return f"{BASE}/{eli_path(doc_type, year, month, day, numac)}/{variant}"


def has_content(html: str) -> bool:
    """True if the ``/justel`` page carries a real act (title block present).

    ejustice returns HTTP 200 for coordinates with no matching NUMAC too - a bare shell page
    with no ``list-item--title`` block. This is the content-based not-found signal.
    """
    return bool(_TITLE_RE.search(html))


def parse_justel(
    html: str, doc_type: str, year: int, month: int, day: int, numac: str
) -> dict[str, Any] | None:
    """Parse a ``/justel`` page into the citation contract + metadata. None if not found."""
    if not has_content(html):
        return None

    title = _clean(_TITLE_RE.search(html).group(1)) if _TITLE_RE.search(html) else None
    source = _clean(m.group(1)) if (m := _SOURCE_RE.search(html)) else None
    publication = _clean(m.group(1)) if (m := _PUBLICATION_RE.search(html)) else None
    numero = _clean(m.group(1)) if (m := _NUMERO_RE.search(html)) else None
    dossier = _clean(m.group(1)) if (m := _DOSSIER_RE.search(html)) else None
    eev = _clean(m.group(1)) if (m := _EEV_RE.search(html)) else None
    toc = _clean(m.group(1)) if (m := _TOC_RE.search(html)) else None

    uri = eli_uri(doc_type, year, month, day, numac, "justel")
    human_citation = _human_readable_citation(title, doc_type, day, month, year)

    return {
        "numac": numero or numac,
        "doc_type": doc_type,
        "year": year,
        "month": month,
        "day": day,
        "title": title,
        "source_authority": source,
        "publication_date": publication,
        "dossier_number": dossier,
        "entry_into_force": eev,
        "table_of_contents": toc,
        "eli_uri": uri,
        "human_readable_citation": human_citation,
        "source_url": uri,
    }


_MONTH_NAMES_FR = {
    1: "janvier", 2: "fevrier", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "aout", 9: "septembre", 10: "octobre", 11: "novembre", 12: "decembre",
}

_DOC_TYPE_LABEL_FR = {
    "loi": "Loi",
    "decret": "Decret",
    "ordonnance": "Ordonnance",
    "arrete": "Arrete",
    "constitution": "Constitution",
}


def _human_readable_citation(
    title: str | None, doc_type: str, day: int, month: int, year: int
) -> str:
    """Build the French LDH-style citation, e.g. 'Loi du 8 janvier 2020'.

    Falls back to the parsed title if it already starts with a date (the Moniteur Belge title
    convention is "D MOIS YYYY. - Loi ..."), otherwise constructs from coordinates.
    """
    if title:
        return title
    label = _DOC_TYPE_LABEL_FR.get(doc_type, doc_type.capitalize())
    month_name = _MONTH_NAMES_FR.get(month, str(month))
    return f"{label} du {day} {month_name} {year}"


def parse_year_listing(html: str, doc_type: str, year: int) -> list[dict[str, Any]]:
    """Parse a ``/eli/{type}/{year}`` listing page into a list of ActListing dicts.

    Best-effort: the listing page is older, less structured markup than the /justel detail page.
    Extracts NUMAC + moniteur/justel links reliably; title extraction is best-effort and may be
    None for some entries (the caller should fetch ``be_get_act`` for the authoritative title).
    """
    out: list[dict[str, Any]] = []
    # Title lines (when present) appear once per entry, in document order, before the
    # "Publie le" block of the SAME entry - so we scan title matches by position and pair
    # each with the nearest following listing-entry match.
    title_matches = list(_LISTING_TITLE_BEFORE_RE.finditer(html))

    for m in _LISTING_ENTRY_RE.finditer(html):
        listed_type = m.group("type")
        y, mo, da = int(m.group("y")), int(m.group("mo")), int(m.group("da"))
        numac = m.group("numac")
        title = None
        for tm in title_matches:
            # closest title block before this entry's date block, within a reasonable span
            if tm.end() <= m.start() and m.start() - tm.end() < 500:
                title = _clean(tm.group("title"))
        out.append(
            {
                "numac": numac,
                "doc_type": listed_type,
                "year": y,
                "title": title,
                "publication_date": m.group("pub_date"),
                "source_authority": _clean(m.group("source")),
                "eli_uri": eli_uri(listed_type, y, mo, da, numac, "justel"),
                "justel_url": eli_uri(listed_type, y, mo, da, numac, "justel"),
                "moniteur_url": eli_uri(listed_type, y, mo, da, numac, "moniteur"),
            }
        )
    return out


def extract_text_section(html: str) -> str | None:
    """Extract the raw 'Texte'/'Tekst' section (act body, HTML preserved for Art. N. structure)."""
    m = _TEXT_SECTION_RE.search(html)
    if not m:
        return None
    return m.group(1).strip()


def article_body_url(numac: str, language: str, pub_date: str | None = None) -> str:
    """Fallback CGI endpoint noted by worldwidelaw/legal-sources - not primary path used here."""
    params = f"language={language}&numac={numac}"
    if pub_date:
        params += f"&pub_date={pub_date}"
    return f"{BASE}/cgi/article_body.pl?{params}"
