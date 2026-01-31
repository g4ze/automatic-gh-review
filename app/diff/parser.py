from __future__ import annotations

import logging

from unidiff import PatchSet

from app.diff.models import DiffFile, DiffHunk, DiffLine

logger = logging.getLogger(__name__)


def _strip_prefix(path: str) -> str:
    """Strip the a/ or b/ prefix that git adds to diff paths."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_diff(raw_diff: str) -> list[DiffFile]:
    """Parse a unified diff string into structured DiffFile objects."""
    patch = PatchSet(raw_diff)
    files: list[DiffFile] = []

    for patched_file in patch:
        diff_file = DiffFile(
            source_file=_strip_prefix(patched_file.source_file),
            target_file=_strip_prefix(patched_file.target_file),
            is_rename=patched_file.is_rename,
            is_binary=patched_file.is_binary_file,
        )

        for hunk in patched_file:
            diff_hunk = DiffHunk(
                source_start=hunk.source_start,
                source_length=hunk.source_length,
                target_start=hunk.target_start,
                target_length=hunk.target_length,
                section_header=hunk.section_header or "",
            )

            for line in hunk:
                diff_line = DiffLine(
                    content=line.value.rstrip("\n"),
                    target_line_number=line.target_line_no,
                    source_line_number=line.source_line_no,
                    is_added=line.is_added,
                    is_removed=line.is_removed,
                    is_context=not line.is_added and not line.is_removed,
                )
                diff_hunk.lines.append(diff_line)

            diff_file.hunks.append(diff_hunk)

        files.append(diff_file)

    logger.debug("Parsed %d files from diff", len(files))
    return files
