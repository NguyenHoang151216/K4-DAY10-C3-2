from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import random
import re
import time
from typing import Any

import requests

from core.config import Settings


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_JITTER_MAX_SECONDS = 0.25


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


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON through a sibling ``.tmp`` file, then atomically replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _retry_after_seconds(response: requests.Response) -> float | None:
    """Parse ``Retry-After`` as delta-seconds or an HTTP date."""

    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _request_headers(settings: Settings) -> dict[str, str]:
    contact = settings.crossref_mailto.strip()
    user_agent = "day10-data-observability-lab/0.1"
    if contact:
        user_agent += f" (mailto:{contact})"
    return {
        # Crossref currently returns HTTP 406 for the vendor media type on
        # some edge nodes; application/json is accepted consistently and the
        # payload schema is unchanged.
        "Accept": "application/json",
        "User-Agent": user_agent,
    }


def _fetch_payload(settings: Settings) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    if settings.crossref_mailto.strip():
        params["mailto"] = settings.crossref_mailto.strip()

    max_retries = max(0, settings.request_max_retries)
    rng = random.Random(settings.random_seed)
    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers=_request_headers(settings),
                timeout=settings.request_timeout_seconds,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            retry_after = None
            reason = type(exc).__name__
        except requests.RequestException as exc:
            raise RuntimeError(f"Crossref request failed without retry: {exc}") from exc
        else:
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                # This raises immediately for 400/401/403/404 as required;
                # those client errors must never consume the retry budget.
                response.raise_for_status()
                try:
                    payload = response.json()
                except (requests.JSONDecodeError, ValueError) as exc:
                    raise ValueError("Crossref returned an invalid JSON response.") from exc
                if not isinstance(payload, dict):
                    raise ValueError("Crossref response JSON must be an object.")
                return payload

            last_error = requests.HTTPError(
                f"Crossref returned retryable HTTP {response.status_code}",
                response=response,
            )
            if attempt >= max_retries:
                break
            retry_after = _retry_after_seconds(response)
            reason = f"HTTP {response.status_code}"

        backoff = float(2**attempt)
        delay = max(backoff, retry_after or 0.0) + rng.uniform(0.0, _JITTER_MAX_SECONDS)
        print(
            f"[crossref] {reason}; retry {attempt + 1}/{max_retries} "
            f"after {delay:.2f}s"
        )
        time.sleep(delay)

    raise RuntimeError(
        f"Crossref request failed after {max_retries + 1} attempts."
    ) from last_error


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records and persist replayable raw lineage snapshots."""

    payload = _fetch_payload(settings)

    # The source snapshot is deliberately persisted before parsing. If a
    # parser/schema regression happens, repair can replay this immutable input
    # without calling Crossref again and silently changing the experiment.
    _atomic_write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError(
            "Crossref returned no valid records with both DOI and title. "
            "Review SOURCE_QUERY/source_filter before continuing."
        )

    _atomic_write_json(
        settings.paths.raw_records_json,
        [asdict(record) for record in records],
    )
    print(
        f"[crossref] fetched {len(records)} records -> "
        f"{settings.paths.raw_records_json}"
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a parsed raw snapshot for deterministic replay and repair."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Raw records snapshot does not exist: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Raw records snapshot is not valid JSON: {path}") from exc

    if not isinstance(payload, list):
        raise ValueError(f"Raw records snapshot must contain a JSON array: {path}")

    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} must be a JSON object.")
        try:
            record = PaperRecord(**item)
        except TypeError as exc:
            raise ValueError(
                f"Raw record at index {index} does not match PaperRecord contract."
            ) from exc
        if not record.paper_id or not record.title:
            raise ValueError(
                f"Raw record at index {index} is missing stable paper_id or title."
            )
        if not isinstance(record.authors, list) or not isinstance(record.categories, list):
            raise ValueError(
                f"Raw record at index {index} must use arrays for authors/categories."
            )
        records.append(record)
    return records
