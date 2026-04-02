"""
API Manager — CRUD operations for Dify API configurations.

Configurations are persisted to a JSON file (data/apis.json) on disk.
Each entry stores:
  - id:           unique slug (derived from the user-given name)
  - name:         human-readable display name
  - base_url:     Dify base URL (e.g. https://api.dify.ai)
  - api_key:      Dify app API key (stored in plaintext for now)
  - inputs:       dict of default input fields
  - created_at:   ISO-8601 timestamp
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ── Storage ──────────────────────────────────────────────────────────────────

_DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent / "data"))
_STORE_PATH = _DATA_DIR / "apis.json"


def _ensure_store() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.exists():
        _STORE_PATH.write_text("[]", encoding="utf-8")


def _load() -> List[Dict]:
    _ensure_store()
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(records: List[Dict]) -> None:
    _ensure_store()
    _STORE_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a display name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\-_]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "api"


def _unique_slug(base: str, existing: List[Dict]) -> str:
    existing_ids = {r["id"] for r in existing}
    slug = base
    if slug not in existing_ids:
        return slug
    for i in range(2, 9999):
        candidate = f"{slug}-{i}"
        if candidate not in existing_ids:
            return candidate
    return f"{slug}-{uuid.uuid4().hex[:6]}"


# ── Public API ────────────────────────────────────────────────────────────────

def create_api(
    name: str,
    base_url: str,
    api_key: str,
    inputs: Optional[Dict] = None,
) -> Dict:
    """Create and persist a new API configuration. Returns the created record."""
    name = name.strip()
    base_url = base_url.rstrip("/").strip()
    if not name:
        raise ValueError("Name must not be empty.")
    if not base_url:
        raise ValueError("Base URL must not be empty.")
    if not api_key:
        raise ValueError("API Key must not be empty.")

    records = _load()

    # Check duplicate name (case-insensitive)
    if any(r["name"].lower() == name.lower() for r in records):
        raise ValueError(f"An API named '{name}' already exists.")

    slug = _unique_slug(_slugify(name), records)

    record = {
        "id": slug,
        "name": name,
        "base_url": base_url,
        "api_key": api_key,
        "inputs": inputs or {},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    records.append(record)
    _save(records)
    return record


def list_apis() -> List[Dict]:
    """Return all stored API configurations."""
    return _load()


def get_api(api_id: str) -> Optional[Dict]:
    """Return a single API config by its ID/slug, or None if not found."""
    return next((r for r in _load() if r["id"] == api_id), None)


def get_api_by_name(name: str) -> Optional[Dict]:
    """Return a single API config by display name (case-insensitive)."""
    return next((r for r in _load() if r["name"].lower() == name.lower()), None)


def update_api(
    api_id: str,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    inputs: Optional[Dict] = None,
) -> Dict:
    """Update an existing API config. Returns the updated record."""
    records = _load()
    idx = next((i for i, r in enumerate(records) if r["id"] == api_id), None)
    if idx is None:
        raise ValueError(f"No API found with id '{api_id}'.")

    rec = records[idx]
    if name is not None:
        name = name.strip()
        # Check duplicate name (excluding current record)
        if any(
            r["name"].lower() == name.lower() and r["id"] != api_id
            for r in records
        ):
            raise ValueError(f"An API named '{name}' already exists.")
        rec["name"] = name
    if base_url is not None:
        rec["base_url"] = base_url.rstrip("/").strip()
    if api_key is not None:
        rec["api_key"] = api_key
    if inputs is not None:
        rec["inputs"] = inputs
    rec["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

    records[idx] = rec
    _save(records)
    return rec


def delete_api(api_id: str) -> bool:
    """Delete an API config by ID. Returns True if deleted, False if not found."""
    records = _load()
    new_records = [r for r in records if r["id"] != api_id]
    if len(new_records) == len(records):
        return False
    _save(new_records)
    return True
