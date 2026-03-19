"""Core analysis logic: auto-fetch verified MPD data, build grounded prompt, parse response."""
from __future__ import annotations

from typing import Any

from models.ollama_client import analyze_async
from mpd_client import (
    extract_ata_chapters,
    extract_task_references,
    get_datasets,
    get_tasks,
    format_reference_block,
)


def parse_analysis(raw: str) -> dict[str, Any]:
    """
    Parse model output into structured fields.
    Works for both grounded (verified data) and ungrounded responses.
    """
    out: dict[str, Any] = {
        "analysis": raw,
        "discrepancies": [],
        "driver": "",
        "recommendations": [],
        "compliance_notes": "",
    }
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        ll = line.lower()
        if ll.startswith(("- discrepancy", "discrepancy:")):
            out["discrepancies"].append(line.split(":", 1)[-1].strip() or line)
        elif ll.startswith(("- driver", "driver:", "- cause", "cause:")):
            out["driver"] = line.split(":", 1)[-1].strip() or line
        elif ll.startswith(("- recommendation", "recommendation:")):
            out["recommendations"].append(line.split(":", 1)[-1].strip() or line)
        elif "compliance" in ll:
            out["compliance_notes"] = (
                line.split(":", 1)[-1].strip() if ":" in line else line
            )
    return out


async def compare_report_mpd(
    report_text: str,
    mpd_context: str = "",
    dataset_id: int | None = None,
) -> dict[str, Any]:
    """
    Analyse report_text against verified MPD data.

    Steps:
    1. Extract ATA chapters + task references from report_text.
    2. If dataset_id provided, query Scopewrath API for matching tasks.
    3. Build grounded reference block → inject into prompt.
    4. Call Ollama → parse response.
    """
    reference_data = ""
    reference_source = ""
    mpd_task_count = 0
    ata_chapters: list[str] = []
    dataset_info: dict | None = None

    if dataset_id is not None:
        ata_chapters = extract_ata_chapters(report_text)
        task_refs = extract_task_references(report_text)

        # If no ATA detected from the text itself, try from the manual mpd_context too
        if not ata_chapters and mpd_context:
            ata_chapters = extract_ata_chapters(mpd_context)
            task_refs += extract_task_references(mpd_context)

        if ata_chapters or task_refs:
            tasks = await get_tasks(
                dataset_id,
                sections=ata_chapters,
                task_references=task_refs,
            )
            if tasks:
                # Get dataset metadata for the source label
                datasets = await get_datasets()
                dataset_info = next((d for d in datasets if d["id"] == dataset_id), None)
                reference_data, reference_source = format_reference_block(
                    tasks, dataset_info, ata_chapters
                )
                mpd_task_count = len(tasks)

    raw = await analyze_async(
        report_text,
        mpd_context=mpd_context,
        reference_data=reference_data,
    )

    result = parse_analysis(raw)
    result["mpd_reference_source"] = reference_source
    result["mpd_task_count"] = mpd_task_count
    result["ata_chapters_queried"] = ata_chapters
    result["dataset_id"] = dataset_id
    return result
