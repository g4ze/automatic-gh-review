from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiffLine:
    """A single line within a diff hunk."""

    content: str
    target_line_number: int | None  # None for deleted lines (only in source)
    source_line_number: int | None  # None for added lines (only in target)
    is_added: bool = False
    is_removed: bool = False
    is_context: bool = False


@dataclass
class DiffHunk:
    """A contiguous hunk within a file diff."""

    source_start: int
    source_length: int
    target_start: int
    target_length: int
    section_header: str
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class DiffFile:
    """A single file's diff, containing one or more hunks."""

    source_file: str
    target_file: str
    is_rename: bool = False
    is_binary: bool = False
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        """The target file path (post-change)."""
        return self.target_file

    @property
    def valid_target_lines(self) -> set[int]:
        """All target-side line numbers present in the diff hunks."""
        result: set[int] = set()
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.target_line_number is not None:
                    result.add(line.target_line_number)
        return result

    @property
    def added_lines(self) -> set[int]:
        """Target line numbers for added lines only."""
        result: set[int] = set()
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.is_added and line.target_line_number is not None:
                    result.add(line.target_line_number)
        return result

    def estimate_tokens(self) -> int:
        line_count = sum(len(h.lines) for h in self.hunks)
        total_chars = sum(len(l.content) for h in self.hunks for l in h.lines)
        return max(line_count, total_chars // 4)
