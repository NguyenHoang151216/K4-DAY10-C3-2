from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


class _JATSTextExtractor(HTMLParser):
    """Extract text from the JATS/HTML fragments returned by Crossref."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)


def _normalize_text(value: Any) -> str:
    """Return a scalar value as clean, single-line text."""

    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def strip_jats(value: Any) -> str:
    """Remove JATS/HTML markup while preserving the abstract's text content."""

    raw_text = _normalize_text(value)
    if not raw_text:
        return ""

    parser = _JATSTextExtractor()
    try:
        parser.feed(raw_text)
        parser.close()
    except (AssertionError, ValueError):
        # HTMLParser is deliberately lenient, but keep a safe fallback for a
        # severely malformed fragment from an upstream publisher.
        return _normalize_text(re.sub(r"<[^>]*>", " ", raw_text))
    return _normalize_text(" ".join(parser.parts))


def _first_text(value: Any) -> str:
    """Read the first usable string from a Crossref scalar/list field."""

    values = value if isinstance(value, list) else [value]
    for item in values:
        text = _normalize_text(item)
        if text:
            return text
    return ""


def _date_parts_to_iso(value: Any) -> str:
    """Convert a Crossref ``date-parts`` object to an ISO date string."""

    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if (
        not isinstance(date_parts, list)
        or not date_parts
        or not isinstance(date_parts[0], list)
    ):
        return ""

    parts = date_parts[0]
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (IndexError, TypeError, ValueError):
        return ""


def _published_date(item: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        published = _date_parts_to_iso(item.get(field))
        if published:
            return published
    return ""


def _updated_date(item: dict[str, Any]) -> str:
    for field in ("indexed", "deposited"):
        value = item.get(field)
        if isinstance(value, dict):
            timestamp = _normalize_text(value.get("date-time"))
            if timestamp:
                return timestamp
            updated = _date_parts_to_iso(value)
            if updated:
                return updated
    return ""


def _authors(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    raw_authors = item.get("author", [])
    if not isinstance(raw_authors, list):
        return result

    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        name = _normalize_text(author.get("name"))
        if not name:
            name = _normalize_text(
                " ".join(
                    part
                    for part in (
                        _normalize_text(author.get("given")),
                        _normalize_text(author.get("family")),
                    )
                    if part
                )
            )
        if name:
            result.append(name)
    return result


def _categories(item: dict[str, Any]) -> list[str]:
    subjects = item.get("subject", [])
    if not isinstance(subjects, list):
        return []
    return [text for subject in subjects if (text := _normalize_text(subject))]


def _pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link", [])
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict):
            continue
        content_type = _normalize_text(link.get("content-type")).lower()
        if content_type in {"application/pdf", "application/x-pdf"}:
            url = _normalize_text(link.get("URL"))
            if url:
                return url
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref response into the frozen ingestion contract.

    ``paper_id`` is the lower-cased DOI. Items without a DOI or title are
    discarded because they cannot satisfy the stable-ID/data-contract rules.
    Missing optional metadata is represented by an empty string/list so that
    downstream cleaning never receives ``None`` values.
    """

    if not isinstance(payload, dict):
        raise TypeError("Crossref payload must be a dictionary.")

    message = payload.get("message", {})
    if not isinstance(message, dict):
        return []
    items = message.get("items", [])
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = _normalize_text(item.get("DOI")).lower()
        title = _first_text(item.get("title"))
        if not paper_id or not title:
            continue

        categories = _categories(item)
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=strip_jats(item.get("abstract")),
                authors=_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=_published_date(item),
                updated=_updated_date(item),
                abs_url=_normalize_text(item.get("URL")),
                pdf_url=_pdf_url(item),
                comment=_first_text(item.get("container-title")),
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    raise NotImplementedError("Student task: implement source fetching.")


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    raise NotImplementedError("Student task: implement raw record loading.")
