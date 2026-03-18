"""Core logic: compare extracted report text vs MPD (DB or file); returns structured analysis."""
from __future__ import annotations

from typing import Any

# App-level ollama client (caller must have perkins root on path or run from app)
from models.ollama_client import analyze_async


# Placeholder: future MPD DB/API call to other VPS
# def fetch_mpd_from_api(ident: str, **params: Any) -> str:
#     r = requests.get("http://other-vps/mpd", params={"task": ident, **params})
#     return r.text if r.ok else ""


def parse_analysis(raw: str) -> dict[str, Any]:
    """Parse model output into structured fields (discrepancies, driver, recommendations, compliance)."""
    out = {
        "analysis": raw,
        "discrepancies": [],
        "driver": "",
        "recommendations": [],
        "compliance_notes": "",
    }
    raw_lower = raw.lower()
    # Extract list-like lines for discrepancies and recommendations
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("- discrepancy") or line.lower().startswith("discrepancy:"):
            out["discrepancies"].append(line.split(":", 1)[-1].strip() or line)
        elif line.lower().startswith("- driver") or line.lower().startswith("driver:"):
            out["driver"] = line.split(":", 1)[-1].strip() or line
        elif line.lower().startswith("- recommendation") or line.lower().startswith("recommendation:"):
            out["recommendations"].append(line.split(":", 1)[-1].strip() or line)
        elif "compliance" in line.lower():
            out["compliance_notes"] = line.split(":", 1)[-1].strip() if ":" in line else line
    if not out["discrepancies"] and "discrepan" in raw_lower:
        out["discrepancies"].append(raw)
    return out


async def compare_report_mpd(
    report_text: str,
    mpd_context: str,
) -> dict[str, Any]:
    """Compare report text vs MPD context via Ollama; return structured JSON-friendly dict."""
    raw = await analyze_async(report_text, mpd_context)
    return parse_analysis(raw)
