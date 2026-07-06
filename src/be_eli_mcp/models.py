"""Pydantic v2 models for Moniteur Belge / Belgisch Staatsblad + be-eli-mcp."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DocType = Literal["loi", "decret", "ordonnance", "arrete", "constitution"]
Language = Literal["fr", "nl", "de"]
TextVariant = Literal["justel", "moniteur"]

DATASET_NOTE = (
    "Moniteur Belge / Belgisch Staatsblad (ejustice.just.fgov.be) is Belgium's official "
    "gazette, keyless and CC0-licensed. Legislation is addressed by ELI coordinates "
    "(type/year/month/day/numac) at /eli/{type}/{yyyy}/{mm}/{dd}/{numac}/justel. There is "
    "no free-text search API - only a year-listing page per legislation type "
    "(/eli/{type}/{year}) for discovery, and get-by-coordinate for full text. Belgium is "
    "trilingual (French/Dutch/German); French is used as the primary human_readable form "
    "by LDH convention, but NL and DE renderings exist for most acts."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ActListing(_Tolerant):
    """One entry from a year-listing page (``be_list_year``)."""

    numac: str | None = None
    doc_type: DocType | None = None
    year: int | None = None
    title: str | None = None
    publication_date: str | None = None
    source_authority: str | None = None
    eli_uri: str | None = None
    justel_url: str | None = None
    moniteur_url: str | None = None


class Act(_Tolerant):
    """Result of ``be_get_act`` - metadata for a Belgian legal resource."""

    numac: str | None = None
    doc_type: DocType | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    title: str | None = None
    source_authority: str | None = None
    publication_date: str | None = None
    dossier_number: str | None = None
    entry_into_force: str | None = None
    table_of_contents: str | None = None
    language: Language = "fr"

    # Citation contract (Art. 4 CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    dataset_note: str = DATASET_NOTE


class LawText(_Tolerant):
    """Result of ``be_get_text`` - the verbatim text of an act."""

    numac: str | None = None
    doc_type: DocType | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    language: Language = "fr"
    variant: TextVariant = "justel"
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    content: str | None = None
    byte_size: int | None = None
    dataset_note: str = DATASET_NOTE
