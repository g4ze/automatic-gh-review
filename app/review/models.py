from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    NITPICK = "nitpick"


SEVERITY_EMOJI = {
    Severity.CRITICAL: "\u2757",      # ❗
    Severity.WARNING: "\u26a0\ufe0f",  # ⚠️
    Severity.SUGGESTION: "\U0001f4a1",  # 💡
    Severity.NITPICK: "\U0001f4ad",    # 💭
}

SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.SUGGESTION: 2,
    Severity.NITPICK: 3,
}


class InlineComment(BaseModel):
    """A single inline comment from the LLM."""

    file: str
    line: int
    severity: Severity
    body: str
    suggestion: str | None = None


class ChunkReviewResult(BaseModel):
    """LLM output for one chunk of the diff."""

    comments: list[InlineComment] = []
    summary: str = ""


class TriageFileEntry(BaseModel):
    """One file's triage assessment from the LLM."""

    file: str
    risk: str  # "high", "medium", "low"
    reason: str


class TriageResult(BaseModel):
    """LLM output for the triage pass."""

    files: list[TriageFileEntry] = []
    summary: str = ""
