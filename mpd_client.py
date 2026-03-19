"""Client for the Scopewrath MPD read-only API at https://mpd.noteify.us."""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

MPD_BASE = os.environ.get("SCOPEWRATH_API_URL", "https://mpd.noteify.us").rstrip("/")
_TIMEOUT = 15.0

# ── ATA / task-reference extraction ──────────────────────────────────────────

# Matches full MPD task references, e.g. 291000-06-1  291000-06-1-L  ZL-131-01-1
_TASK_RE = re.compile(
    r"\b([A-Z]{0,3}\d{5,6}-[A-Z0-9]{2}-\d+(?:-[A-Z0-9]{1,2})?)\b"
)

# ATA chapter from first two digits of a numeric task ref, e.g. 291000 → "29"
_ATA_FROM_TASK_RE = re.compile(r"^\d{2}")

# Explicit "ATA 32" or "ATA32" mentions
_ATA_EXPLICIT_RE = re.compile(r"\bATA[\s-]?(\d{2})\b", re.IGNORECASE)


def extract_ata_chapters(text: str) -> list[str]:
    """Return sorted list of unique ATA chapter strings found in text."""
    chapters: set[str] = set()

    for m in _ATA_EXPLICIT_RE.finditer(text):
        chapters.add(m.group(1).lstrip("0") or "0")

    for m in _TASK_RE.finditer(text):
        ref = m.group(1)
        m2 = _ATA_FROM_TASK_RE.match(ref)
        if m2:
            chapters.add(m2.group(0).lstrip("0") or "0")

    return sorted(chapters, key=lambda x: int(x) if x.isdigit() else 0)


def extract_task_references(text: str) -> list[str]:
    """Return sorted unique task references found in text."""
    return sorted({m.group(1) for m in _TASK_RE.finditer(text)})


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


async def get_tasks(
    dataset_id: int,
    *,
    sections: list[str] | None = None,
    task_references: list[str] | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch MPD tasks for a dataset.
    If sections provided, fetches one batch per section.
    If task_references provided and sections empty, derives sections automatically.
    """
    all_tasks: dict[int, dict] = {}  # id → task, dedup

    atas_to_fetch: list[str] = list(sections or [])

    # Also derive ATA from explicit task references
    if task_references:
        for ref in task_references:
            m = _ATA_FROM_TASK_RE.match(ref)
            if m:
                ata = m.group(0).lstrip("0") or "0"
                if ata not in atas_to_fetch:
                    atas_to_fetch.append(ata)

    if not atas_to_fetch:
        return []

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for section in atas_to_fetch:
            try:
                r = await client.get(
                    f"{MPD_BASE}/api/mpd/datasets/{dataset_id}/tasks",
                    params={"section": section, "limit": limit},
                )
                r.raise_for_status()
                for t in r.json():
                    all_tasks[t["id"]] = t
            except Exception:
                continue

    return list(all_tasks.values())


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
