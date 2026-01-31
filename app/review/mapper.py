from __future__ import annotations

import logging

from app.diff.models import DiffFile
from app.github.models import ReviewComment
from app.review.models import (
    ChunkReviewResult,
    InlineComment,
    Severity,
    SEVERITY_EMOJI,
    SEVERITY_RANK,
)

logger = logging.getLogger(__name__)

SNAP_THRESHOLD = 3  # Maximum lines to snap to nearest valid line


def _snap_line(line: int, valid_lines: set[int]) -> int | None:
    """Snap a line number to the nearest valid diff line within threshold.

    Returns None if no valid line is close enough.
    """
    if line in valid_lines:
        return line

    if not valid_lines:
        return None

    closest = min(valid_lines, key=lambda v: abs(v - line))
    if abs(closest - line) <= SNAP_THRESHOLD:
        logger.debug("Snapped line %d → %d", line, closest)
        return closest

    logger.warning("Line %d has no valid neighbor (nearest=%d), dropping", line, closest)
    return None


def validate_and_map_comments(
    chunk_result: ChunkReviewResult,
    diff_files: list[DiffFile],
) -> list[ReviewComment]:
    """Map LLM inline comments to GitHub review comment format.

    Validates that each comment's line number falls within a diff hunk.
    Snaps slightly off-target lines to the nearest valid line.
    Drops comments that can't be mapped.
    """
    # Build lookup: file path → set of valid target line numbers
    valid_lines_by_file: dict[str, set[int]] = {}
    for f in diff_files:
        valid_lines_by_file[f.path] = f.valid_target_lines

    result: list[ReviewComment] = []

    for comment in chunk_result.comments:
        valid_lines = valid_lines_by_file.get(comment.file)

        if valid_lines is None:
            logger.warning(
                "Comment references unknown file %r, dropping", comment.file
            )
            continue

        snapped = _snap_line(comment.line, valid_lines)
        if snapped is None:
            logger.warning(
                "Comment on %s:%d cannot be mapped to diff, dropping",
                comment.file,
                comment.line,
            )
            continue

        body = _format_comment_body(comment)

        result.append(
            ReviewComment(
                path=comment.file,
                line=snapped,
                side="RIGHT",
                body=body,
            )
        )

    return result


def _format_comment_body(comment: InlineComment) -> str:
    """Format an inline comment with severity emoji and optional suggestion."""
    emoji = SEVERITY_EMOJI.get(comment.severity, "")
    parts = [f"{emoji} **{comment.severity.value.upper()}**: {comment.body}"]

    if comment.suggestion:
        parts.append(f"\n```suggestion\n{comment.suggestion}\n```")

    return "\n".join(parts)


def deduplicate_comments(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Merge duplicate comments that reference the same file:line with similar body."""
    seen: dict[tuple[str, int], ReviewComment] = {}

    for c in comments:
        key = (c.path, c.line)
        if key in seen:
            # Append body if it's substantially different
            existing = seen[key]
            if c.body not in existing.body:
                seen[key] = ReviewComment(
                    path=c.path,
                    line=c.line,
                    side=c.side,
                    body=f"{existing.body}\n\n---\n\n{c.body}",
                )
        else:
            seen[key] = c

    return list(seen.values())


def enforce_comment_budget(
    comments: list[ReviewComment],
    max_comments: int,
    inline_comments_source: list[InlineComment],
) -> tuple[list[ReviewComment], list[str]]:
    """Keep highest-severity comments within budget, consolidate overflow into summary.

    Returns (kept_comments, overflow_summary_lines).
    """
    if len(comments) <= max_comments:
        return comments, []

    # Build severity lookup for ReviewComments by (path, line)
    severity_lookup: dict[tuple[str, int], Severity] = {}
    for ic in inline_comments_source:
        severity_lookup[(ic.file, ic.line)] = ic.severity

    def sort_key(c: ReviewComment) -> int:
        sev = severity_lookup.get((c.path, c.line), Severity.NITPICK)
        return SEVERITY_RANK.get(sev, 99)

    sorted_comments = sorted(comments, key=sort_key)
    kept = sorted_comments[:max_comments]
    overflow = sorted_comments[max_comments:]

    overflow_lines: list[str] = []
    for c in overflow:
        # Truncate body for summary
        short_body = c.body[:120].split("\n")[0]
        overflow_lines.append(f"- **{c.path}:{c.line}** — {short_body}")

    return kept, overflow_lines
