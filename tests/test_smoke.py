"""Smoke tests - require internet, hit the live ejustice.just.fgov.be.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import pytest

from be_eli_mcp.server import be_get_act, be_get_text, be_list_year

# Loi du 8 janvier 2020 fixant le contingent de l'armee pour l'annee 2020.
DOC_TYPE = "loi"
YEAR = 2020
MONTH = 1
DAY = 8
NUMAC = "2020040054"


@pytest.mark.asyncio
async def test_smoke_get_act() -> None:
    act = await be_get_act(doc_type=DOC_TYPE, year=YEAR, month=MONTH, day=DAY, numac=NUMAC)
    assert act.eli_uri and act.eli_uri.endswith(f"{NUMAC}/justel")
    assert act.numac == NUMAC
    assert act.title and "contingent" in act.title.lower()
    assert act.human_readable_citation
    assert act.source_url and act.source_url.startswith("https://www.ejustice.just.fgov.be/")
    assert act.publication_date


@pytest.mark.asyncio
async def test_smoke_get_text_fr() -> None:
    text = await be_get_text(doc_type=DOC_TYPE, year=YEAR, month=MONTH, day=DAY, numac=NUMAC)
    assert text.content and "Article" in text.content
    assert text.byte_size and text.byte_size > 0
    assert text.eli_uri and text.eli_uri.endswith(f"{NUMAC}/justel")
    assert text.language == "fr"


@pytest.mark.asyncio
async def test_smoke_get_text_nl() -> None:
    text = await be_get_text(
        doc_type=DOC_TYPE, year=YEAR, month=MONTH, day=DAY, numac=NUMAC, language="nl"
    )
    assert text.content
    assert text.language == "nl"


@pytest.mark.asyncio
async def test_smoke_list_year() -> None:
    listings = await be_list_year(doc_type=DOC_TYPE, year=YEAR)
    assert len(listings) > 10
    assert any(entry.numac == NUMAC for entry in listings)


@pytest.mark.asyncio
async def test_smoke_not_found() -> None:
    from be_eli_mcp.server import ToolError

    with pytest.raises(ToolError) as exc_info:
        await be_get_act(doc_type=DOC_TYPE, year=YEAR, month=MONTH, day=DAY, numac="9999999999")
    assert exc_info.value.code == "not_found"
