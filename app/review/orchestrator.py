from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import Settings
from app.diff.chunker import DiffChunk, chunk_diff_files
from app.diff.models import DiffFile
from app.diff.parser import parse_diff
from app.github import client as gh
from app.github.models import ReviewComment, ReviewSubmission
from app.review.llm_client import LLMParseError, call_llm_json
from app.review.mapper import (
    deduplicate_comments,
    enforce_comment_budget,
    validate_and_map_comments,
)
from app.review.models import (
    ChunkReviewResult,
    InlineComment,
    Severity,
    TriageResult,
)
from app.review.prompt_builder import build_review_prompt, build_triage_prompt

logger = logging.getLogger(__name__)

# Token thresholds for tiered strategy
SMALL_THRESHOLD = 6_000
LARGE_THRESHOLD = 50_000
HUGE_THRESHOLD = 100_000


async def run_review(
    settings: Settings,
    http_client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    extra_instructions: str = "",
) -> None:
    """Main review orchestrator. Runs as a background task."""
    try:
        await _run_review_inner(
            settings, http_client, owner, repo, pr_number, extra_instructions
        )
    except Exception:
        logger.exception("Review failed for %s/%s#%d", owner, repo, pr_number)


async def _run_review_inner(
    settings: Settings,
    http_client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    extra_instructions: str,
) -> None:
    # 1. Fetch PR details and diff
    pr = await gh.get_pr_details(http_client, owner, repo, pr_number)
    raw_diff = await gh.get_pr_diff(http_client, owner, repo, pr_number)

    # 2. Parse diff
    all_files = parse_diff(raw_diff)

    # 3. Filter ignored files
    files = [f for f in all_files if not settings.should_ignore_file(f.path)]
    ignored_count = len(all_files) - len(files)
    if ignored_count:
        logger.info("Filtered out %d ignored files", ignored_count)

    if not files:
        logger.info("No reviewable files in diff, skipping")
        return

    # 4. Estimate total tokens
    total_tokens = sum(f.estimate_tokens() for f in files)
    logger.info("Diff: %d files, ~%d tokens", len(files), total_tokens)

    # 5. Bail if too large
    if total_tokens > HUGE_THRESHOLD:
        summary = (
            f"This PR is very large (~{total_tokens} tokens across {len(files)} files). "
            "Please consider splitting it into smaller PRs for a more effective review."
        )
        review = ReviewSubmission(
            commit_id=pr.head_sha,
            body=summary,
            event="COMMENT",
            comments=[],
        )
        await gh.post_review(http_client, owner, repo, pr_number, review)
        return

    # 6. Fetch review rules
    rules = await gh.get_file_content(
        http_client, owner, repo, settings.review_rules_path, pr.default_branch
    )

    # 7. Choose strategy based on size
    if total_tokens <= SMALL_THRESHOLD:
        comments, summary_parts = await _review_small(
            settings, files, all_files, rules, extra_instructions
        )
    elif total_tokens <= LARGE_THRESHOLD:
        comments, summary_parts = await _review_medium(
            settings, files, all_files, rules, extra_instructions
        )
    else:
        comments, summary_parts = await _review_large(
            settings, files, all_files, rules, extra_instructions
        )

    # 8. Post-process comments
    comments = deduplicate_comments(comments)

    # Collect all InlineComment objects for severity lookup during budget enforcement
    all_inline = _extract_inline_from_review_comments(comments, files)

    kept, overflow = enforce_comment_budget(
        comments, settings.max_comments_per_review, all_inline
    )

    # 9. Build summary
    summary_body = _build_summary(summary_parts, overflow, len(files), ignored_count)

    # 10. Determine event type
    has_critical = any(
        "**CRITICAL**" in c.body for c in kept
    )
    event = "REQUEST_CHANGES" if has_critical else "COMMENT"

    # 11. Post review
    review = ReviewSubmission(
        commit_id=pr.head_sha,
        body=summary_body,
        event=event,
        comments=kept,
    )
    await gh.post_review(http_client, owner, repo, pr_number, review)
    logger.info("Review posted: %d comments, event=%s", len(kept), event)


async def _review_small(
    settings: Settings,
    files: list[DiffFile],
    all_files: list[DiffFile],
    rules: str | None,
    extra_instructions: str,
) -> tuple[list[ReviewComment], list[str]]:
    """Single-call review for small diffs."""
    system, user = build_review_prompt(files, all_files, rules, extra_instructions)
    result = await _call_and_parse_review(settings, system, user)
    comments = validate_and_map_comments(result, files)
    return comments, [result.summary]


async def _review_medium(
    settings: Settings,
    files: list[DiffFile],
    all_files: list[DiffFile],
    rules: str | None,
    extra_instructions: str,
) -> tuple[list[ReviewComment], list[str]]:
    """Chunked parallel review for medium diffs."""
    chunks = chunk_diff_files(files, settings.max_diff_tokens_per_chunk)
    semaphore = asyncio.Semaphore(settings.max_concurrent_chunks)

    async def review_chunk(chunk: DiffChunk) -> tuple[list[ReviewComment], str]:
        async with semaphore:
            system, user = build_review_prompt(
                chunk.files, all_files, rules, extra_instructions
            )
            result = await _call_and_parse_review(settings, system, user)
            mapped = validate_and_map_comments(result, chunk.files)
            return mapped, result.summary

    tasks = [review_chunk(chunk) for chunk in chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_comments: list[ReviewComment] = []
    summaries: list[str] = []

    for r in results:
        if isinstance(r, Exception):
            logger.error("Chunk review failed: %s", r)
            summaries.append(f"(One chunk failed to review: {r})")
            continue
        chunk_comments, chunk_summary = r
        all_comments.extend(chunk_comments)
        summaries.append(chunk_summary)

    return all_comments, summaries


async def _review_large(
    settings: Settings,
    files: list[DiffFile],
    all_files: list[DiffFile],
    rules: str | None,
    extra_instructions: str,
) -> tuple[list[ReviewComment], list[str]]:
    """Two-pass review: triage then targeted review of high-risk files."""
    # Pass 1: Triage
    system, user = build_triage_prompt(files)
    try:
        triage_raw = await call_llm_json(settings, system, user)
        triage = TriageResult.model_validate(triage_raw)
    except (LLMParseError, Exception) as exc:
        logger.error("Triage failed, falling back to medium strategy: %s", exc)
        return await _review_medium(
            settings, files, all_files, rules, extra_instructions
        )

    # Select high/medium risk files
    high_risk_paths = {
        e.file for e in triage.files if e.risk in ("high", "medium")
    }
    target_files = [f for f in files if f.path in high_risk_paths]

    # Limit to max_files_deep_review
    if len(target_files) > settings.max_files_deep_review:
        target_files = target_files[: settings.max_files_deep_review]

    if not target_files:
        # If triage found nothing, review all files as medium
        return await _review_medium(
            settings, files, all_files, rules, extra_instructions
        )

    # Pass 2: Targeted review
    comments, summaries = await _review_medium(
        settings, target_files, all_files, rules, extra_instructions
    )

    # Add triage context to summary
    skipped_files = [f.path for f in files if f.path not in high_risk_paths]
    if skipped_files:
        summaries.append(
            f"**Triage summary**: {len(skipped_files)} low-risk files were "
            f"skipped (e.g., {', '.join(skipped_files[:5])})"
        )
    summaries.insert(0, triage.summary)

    return comments, summaries


async def _call_and_parse_review(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
) -> ChunkReviewResult:
    """Call LLM and parse the response into a ChunkReviewResult."""
    try:
        raw = await call_llm_json(settings, system_prompt, user_prompt)
        return ChunkReviewResult.model_validate(raw)
    except LLMParseError:
        logger.error("Failed to parse LLM review response after retries")
        return ChunkReviewResult(comments=[], summary="(Failed to parse LLM response)")
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return ChunkReviewResult(comments=[], summary=f"(LLM call failed: {exc})")


def _extract_inline_from_review_comments(
    review_comments: list[ReviewComment],
    diff_files: list[DiffFile],
) -> list[InlineComment]:
    """Reconstruct InlineComment objects from ReviewComments for severity lookup."""
    result: list[InlineComment] = []
    for rc in review_comments:
        # Parse severity from the body
        severity = Severity.SUGGESTION
        for s in Severity:
            if f"**{s.value.upper()}**" in rc.body:
                severity = s
                break
        result.append(
            InlineComment(
                file=rc.path,
                line=rc.line,
                severity=severity,
                body=rc.body,
            )
        )
    return result


def _build_summary(
    summary_parts: list[str],
    overflow_lines: list[str],
    file_count: int,
    ignored_count: int,
) -> str:
    """Build the final review summary body."""
    sections: list[str] = []

    sections.append(f"## Automated Code Review\n\nReviewed {file_count} file(s).")
    if ignored_count:
        sections.append(f"_{ignored_count} file(s) were skipped (matched ignore patterns)._")

    # Chunk summaries
    for i, part in enumerate(summary_parts):
        if part:
            if len(summary_parts) > 1:
                sections.append(f"**Part {i + 1}**: {part}")
            else:
                sections.append(part)

    # Overflow comments
    if overflow_lines:
        sections.append(
            "\n### Additional findings (over comment budget)\n"
            + "\n".join(overflow_lines)
        )

    sections.append(
        "\n---\n_Generated by automatic-gh-review_"
    )

    return "\n\n".join(sections)
