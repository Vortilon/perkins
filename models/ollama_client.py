"""Ollama client wrapper for Perkins AI (perkins-ai model)."""
import httpx

OLLAMA_BASE = "http://127.0.0.1:11434"
MODEL = "perkins-ai"
TIMEOUT = 180.0


def _build_prompt(
    report_text: str,
    mpd_context: str = "",
    reference_data: str = "",
) -> str:
    """
    Build the final prompt sent to the model.

    Priority:
    1. reference_data (verified from MPD API) → strict grounded prompt
    2. mpd_context (manually pasted)          → comparison prompt
    3. Neither                                 → general technical assistant
    """
    if reference_data:
        return (
            f"{reference_data}\n\n"
            "DOCUMENT / QUERY TO ANALYSE:\n"
            f"{report_text}\n\n"
            "Instructions:\n"
            "- For every task reference in the document, look it up in the VERIFIED MPD "
            "REFERENCE DATA table above.\n"
            "- If found: state the exact interval, threshold, and applicability from the table. "
            "Do not modify these values.\n"
            "- If NOT found in the table: state exactly 'Task [ref] not found in MPD reference "
            "data.' — do not guess or invent values.\n"
            "- Identify discrepancies between what the document states and what the table shows.\n"
            "- Summarise findings, drivers, recommendations, and compliance notes.\n"
            "- Never invent task numbers, intervals, thresholds, or applicability that are not "
            "in the table.\n\n"
            "Analysis:"
        )

    if mpd_context and mpd_context.strip() not in ("No MPD context provided.", ""):
        return (
            "DOCUMENT TO ANALYSE:\n"
            f"{report_text}\n\n"
            "MPD CONTEXT (provided manually — treat as reference, not verified):\n"
            f"{mpd_context}\n\n"
            "Compare the document against the MPD context. Identify discrepancies, drivers, "
            "recommendations, and compliance notes. Flag any task reference you cannot verify "
            "from the MPD context provided above.\n\n"
            "Analysis:"
        )

    return (
        f"{report_text}\n\n"
        "Provide a technical response. If this contains maintenance task data, identify "
        "relevant findings. If it is a general question, answer directly and accurately. "
        "If you are not certain of a specific task number, interval, or regulatory reference, "
        "say so explicitly rather than guessing.\n\n"
        "Response:"
    )


def analyze(
    report_text: str,
    mpd_context: str = "",
    reference_data: str = "",
    *,
    timeout: float = TIMEOUT,
) -> str:
    """Call perkins-ai model; return raw response text."""
    prompt = _build_prompt(report_text, mpd_context, reference_data)
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


async def analyze_async(
    report_text: str,
    mpd_context: str = "",
    reference_data: str = "",
    *,
    timeout: float = TIMEOUT,
) -> str:
    """Async version for FastAPI."""
    prompt = _build_prompt(report_text, mpd_context, reference_data)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


def ping() -> bool:
    """Check if Ollama is reachable."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
