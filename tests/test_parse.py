"""Offline tests - parse live-captured fixtures (tests/fixtures/), no network."""

from __future__ import annotations

from pathlib import Path

from be_eli_mcp import citations

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_justel_fixture() -> None:
    html = _read("justel_loi_2020040054.html")
    rec = citations.parse_justel(html, "loi", 2020, 1, 8, "2020040054")
    assert rec is not None
    assert rec["numac"] == "2020040054"
    assert rec["doc_type"] == "loi"
    assert "contingent" in rec["title"].lower()
    assert rec["source_authority"] == "Défense Nationale"
    assert rec["publication_date"] == "22 janvier 2020"
    assert rec["dossier_number"] == "2020-01-08/05"
    assert rec["entry_into_force"] == "1 janvier 2020"
    assert rec["eli_uri"] == (
        "https://www.ejustice.just.fgov.be/eli/loi/2020/01/08/2020040054/justel"
    )
    assert rec["source_url"] == rec["eli_uri"]
    assert rec["human_readable_citation"]


def test_has_content_true_for_real_fixture() -> None:
    html = _read("justel_loi_2020040054.html")
    assert citations.has_content(html) is True


def test_has_content_false_for_notfound_fixture() -> None:
    html = _read("justel_notfound.html")
    assert citations.has_content(html) is False


def test_parse_justel_returns_none_for_notfound() -> None:
    html = _read("justel_notfound.html")
    rec = citations.parse_justel(html, "loi", 2020, 1, 8, "9999999999")
    assert rec is None


def test_extract_text_section() -> None:
    html = _read("justel_loi_2020040054.html")
    text = citations.extract_text_section(html)
    assert text is not None
    assert "Article" in text
    assert "1er" in text


def test_parse_year_listing() -> None:
    html = _read("year_listing_loi_2020.html")
    entries = citations.parse_year_listing(html, "loi", 2020)
    assert len(entries) > 50
    numacs = {e["numac"] for e in entries}
    assert "2020040054" in numacs
    match = next(e for e in entries if e["numac"] == "2020040054")
    assert match["title"] is not None
    assert "contingent" in match["title"].lower()
    assert match["eli_uri"].endswith("/justel")
    assert match["moniteur_url"].endswith("/moniteur")


def test_eli_uri_construction() -> None:
    uri = citations.eli_uri("loi", 2020, 1, 8, "2020040054", "justel")
    assert uri == "https://www.ejustice.just.fgov.be/eli/loi/2020/01/08/2020040054/justel"
