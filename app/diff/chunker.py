from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.diff.models import DiffFile

logger = logging.getLogger(__name__)


@dataclass
class DiffChunk:
    """A group of DiffFiles that fits within a token budget."""

    files: list[DiffFile] = field(default_factory=list)
    token_estimate: int = 0

    def add_file(self, f: DiffFile) -> None:
        tokens = f.estimate_tokens()
        self.files.append(f)
        self.token_estimate += tokens


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def build_file_manifest(all_files: list[DiffFile]) -> str:
    """Build a manifest header listing all files in the PR."""
    lines = ["## Files in this PR:"]
    for f in all_files:
        prefix = "+" if any(l.is_added for h in f.hunks for l in h.lines) else "~"
        lines.append(f"  {prefix} {f.path}")
    return "\n".join(lines)


def chunk_diff_files(
    files: list[DiffFile],
    max_tokens_per_chunk: int,
) -> list[DiffChunk]:
    """Split diff files into chunks that each fit under the token budget.

    Strategy:
    - Keep all hunks of a single file together when possible.
    - If a single file exceeds the budget, split it at hunk boundaries.
    - Each chunk includes a file manifest header for cross-file awareness.
    """
    # Reserve tokens for the manifest header
    manifest_tokens = estimate_tokens(build_file_manifest(files))
    budget = max_tokens_per_chunk - manifest_tokens - 200  # margin

    if budget < 500:
        budget = 500

    chunks: list[DiffChunk] = []
    current = DiffChunk()

    for f in files:
        file_tokens = f.estimate_tokens()

        if file_tokens == 0:
            continue

        # File fits in current chunk
        if current.token_estimate + file_tokens <= budget:
            current.add_file(f)
            continue

        # File fits in a new chunk by itself
        if file_tokens <= budget:
            if current.files:
                chunks.append(current)
            current = DiffChunk()
            current.add_file(f)
            continue

        # File is too big — split at hunk boundaries
        if current.files:
            chunks.append(current)
            current = DiffChunk()

        for hunk in f.hunks:
            hunk_tokens = sum(len(l.content) for l in hunk.lines) // 4
            if current.token_estimate + hunk_tokens > budget and current.files:
                chunks.append(current)
                current = DiffChunk()

            # Create a single-hunk DiffFile fragment
            fragment = DiffFile(
                source_file=f.source_file,
                target_file=f.target_file,
                is_rename=f.is_rename,
                is_binary=f.is_binary,
                hunks=[hunk],
            )
            current.add_file(fragment)

    if current.files:
        chunks.append(current)

    logger.info(
        "Split %d files into %d chunks (budget=%d tokens/chunk)",
        len(files),
        len(chunks),
        max_tokens_per_chunk,
    )
    return chunks
