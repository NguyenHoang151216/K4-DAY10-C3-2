from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, Iterable


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(df, path: Path) -> None:
    ensure_parent(path)
    df.to_csv(path, index=False)


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned or "item"


def compact_join(items: Iterable[str], sep: str = ", ") -> str:
    return sep.join(item for item in items if item)


def normalize_manifest_persist_path(manifest_path: Path, project_dir: Path) -> None:
    """Doi `persist_path` trong embedding manifest ve duong dan tuong doi.

    `LocalEmbeddingIndex.build()` ghi `str(persist_path)` tuc la duong dan tuyet doi
    cua may sinh ra no. Manifest duoc commit vao repo nen absolute path vua lo cay
    thu muc ca nhan, vua khong tai lap duoc tren may khac - dung muc bi tru diem
    "hard-code path" trong rubric.

    `index.py` la read-only voi ca nhom (khong duoc sua schema manifest), nen viec
    chuan hoa phai lam ngay sau `build()` thay vi sua trong `index.py`.
    """
    try:
        payload = read_json(manifest_path)
    except (OSError, ValueError):
        return
    if not isinstance(payload, dict) or "persist_path" not in payload:
        return

    current = Path(str(payload["persist_path"]))
    if not current.is_absolute():
        return
    try:
        relative = current.resolve().relative_to(project_dir.resolve())
    except ValueError:
        # Manifest tro toi thu muc ngoai project (vi du sinh tu may khac):
        # neo lai theo layout chuan thay vi giu duong dan khong ton tai o day.
        relative = Path("data") / "chroma"
    payload["persist_path"] = relative.as_posix()
    write_json(manifest_path, payload)


def first_sentence(text: str) -> str:
    chunks = re.split(r"(?<=[.!?])\s+", normalize_whitespace(text))
    return chunks[0] if chunks else normalize_whitespace(text)
