"""Client for the Scopewrath MPD read-only API at https://mpd.noteify.us."""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

MPD_BASE = os.environ.get("SCOPEWRATH_API_URL", "https://mpd.noteify.us").rstrip("/")
_TIMEOUT = 20.0

# ── ATA / task-reference extraction ──────────────────────────────────────────

# Airbus-style:  291000-06-1  291000-06-1-L  ZL-131-01-1
# ATR-style:     122111-CLN-10000-1   321211-CHK-10000-1
# Boeing-style:  20-001-00   32-011-00   05-12-09-1
_TASK_RE = re.compile(
    r"\b([A-Z]{0,3}\d{5,6}-(?:[A-Z]{2,3}|\d{2})-[A-Z0-9]+-?\d*(?:-[A-Z0-9]{1,2})?)"
    r"|(\d{2}-\d{3}-\d{2}(?:-\d+)?)\b"
)

# ATA chapter = first two digits of the numeric prefix (both formats)
_ATA_FROM_TASK_RE = re.compile(r"^\d{2}")

# Explicit "ATA 32" or "ATA32" mentions
_ATA_EXPLICIT_RE = re.compile(r"\bATA[\s-]?(\d{2})\b", re.IGNORECASE)

# Simple cache: dataset_id → list of all tasks (refreshed per process startup)
_task_cache: dict[int, list[dict]] = {}


def _match_to_ref(m: re.Match) -> str:
    """Return the task reference string from a regex match (handles alternation)."""
    return m.group(1) or m.group(2) or ""


def extract_ata_chapters(text: str) -> list[str]:
    """Return sorted list of unique ATA chapter strings found in text."""
    chapters: set[str] = set()

    for m in _ATA_EXPLICIT_RE.finditer(text):
        chapters.add(m.group(1).lstrip("0") or "0")

    for m in _TASK_RE.finditer(text):
        ref = _match_to_ref(m)
        m2 = _ATA_FROM_TASK_RE.match(ref)
        if m2:
            chapters.add(m2.group(0).lstrip("0") or "0")

    return sorted(chapters, key=lambda x: int(x) if x.isdigit() else 0)


def extract_task_references(text: str) -> list[str]:
    """Return sorted unique task references found in text."""
    return sorted({_match_to_ref(m) for m in _TASK_RE.finditer(text) if _match_to_ref(m)})


# ── API calls ─────────────────────────────────────────────────────────────────

async def get_datasets() -> list[dict[str, Any]]:
    """Return list of available MPD datasets."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"{MPD_BASE}/api/mpd/datasets")
            r.raise_for_status()
            return r.json()
    except Exception:
        return []


async def _fetch_all_tasks(dataset_id: int) -> list[dict[str, Any]]:
    """
    Fetch ALL tasks for a dataset in one call (max 1000 per page).
    Results are cached in _task_cache for the process lifetime.
    """
    if dataset_id in _task_cache:
        return _task_cache[dataset_id]

    all_tasks: list[dict] = []
    offset = 0
    batch = 1000
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while True:
            try:
                r = await client.get(
                    f"{MPD_BASE}/api/mpd/datasets/{dataset_id}/tasks",
                    params={"limit": batch, "offset": offset},
                )
                r.raise_for_status()
                page = r.json()
                if not page:
                    break
                all_tasks.extend(page)
                if len(page) < batch:
                    break
                offset += batch
            except Exception:
                break

    _task_cache[dataset_id] = all_tasks
    return all_tasks


async def get_tasks(
    dataset_id: int,
    *,
    sections: list[str] | None = None,
    task_references: list[str] | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Return MPD tasks matching the given ATA chapters (sections) and/or task references.

    ATA chapter matching works for both:
    - Airbus format: 291000-06-1 → ATA "29" (first 2 digits of 6-digit prefix)
    - ATR format:    321211-CHK-10000-1 → ATA "32" (first 2 digits of 6-digit prefix)
    The API's `section` field uses manufacturer-internal numbering, so we fetch
    all tasks once and filter locally by task_reference prefix.
    """
    all_tasks = await _fetch_all_tasks(dataset_id)
    if not all_tasks:
        return []

    # Build ATA chapter set to filter by
    ata_set: set[str] = set(sections or [])
    if task_references:
        for ref in task_references:
            m = _ATA_FROM_TASK_RE.match(ref)
            if m:
                ata_set.add(m.group(0).lstrip("0") or "0")

    if not ata_set:
        return []

    # Filter: task_reference starts with any requested ATA chapter (2-digit prefix)
    # Works for Airbus (291000-06-1), ATR (321211-CHK-10000-1), Boeing (20-001-00)
    matched: list[dict] = []
    for t in all_tasks:
        ref = t.get("task_reference") or t.get("task_number") or ""
        m = _ATA_FROM_TASK_RE.match(ref)
        if m and (m.group(0).lstrip("0") or "0") in ata_set:
            matched.append(t)
        if len(matched) >= limit:
            break

    return matched


# ── Formatting for prompt injection ──────────────────────────────────────────

def format_reference_block(
    tasks: list[dict[str, Any]],
    dataset: dict[str, Any] | None,
    ata_chapters: list[str],
) -> tuple[str, str]:
    """
    Returns (reference_block, source_label).
    reference_block is the text to inject into the AI prompt.
    source_label is a short citation string for the UI.
    """
    if not tasks:
        return "", ""

    d = dataset or {}
    source_label = (
        f"{d.get('manufacturer', '')} {d.get('model', '')} MPD"
        f" Rev. {d.get('revision', 'unknown')}"
        f" (dataset_id={d.get('id', '?')})"
    ).strip()

    chapters_str = ", ".join(f"ATA {c}" for c in ata_chapters) or "all"

    lines = [
        "╔══ VERIFIED MPD REFERENCE DATA ══════════════════════════════════════",
        f"║  Source : {source_label}",
        f"║  ATA    : {chapters_str}",
        f"║  Rows   : {len(tasks)}",
        "║  INSTRUCTION: Only cite task references from this table.",
        "║  If a task is not listed here, state 'Not found in MPD reference data.'",
        "╠══ task_reference ─── title ─────────────────── interval_raw ──── applicability",
    ]

    for t in tasks:
        ref = (t.get("task_reference") or t.get("task_number") or "?")[:20]
        title = (t.get("title") or t.get("description") or "")[:55]
        interval = (t.get("interval_raw") or t.get("interval_normalized") or "")[:20]
        applicability = (t.get("applicability_raw") or "")[:30]
        threshold = (t.get("threshold_raw") or "")[:15]
        lines.append(
            f"║  {ref:<20}  {title:<55}  {threshold:<15}  {interval:<20}  {applicability}"
        )

    lines.append("╚══ END VERIFIED MPD REFERENCE DATA ══════════════════════════════════")
    return "\n".join(lines), source_label
