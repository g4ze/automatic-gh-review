from __future__ import annotations

from app.diff.chunker import build_file_manifest
from app.diff.models import DiffFile


REVIEW_SYSTEM_PROMPT = """\
You are an expert code reviewer. You review pull request diffs and produce structured JSON output.

## Response Format

You MUST respond with a valid JSON object matching this schema:

```json
{{
  "comments": [
    {{
      "file": "path/to/file.py",
      "line": 42,
      "severity": "critical|warning|suggestion|nitpick",
      "body": "Clear explanation of the issue.",
      "suggestion": "Optional: replacement code for a GitHub suggestion block (just the replacement lines, no fences)."
    }}
  ],
  "summary": "Brief overall assessment of this diff chunk."
}}
```

## Rules

1. The `line` field MUST be one of the annotated line numbers shown in the diff (the number before the `|` pipe character).
2. Only comment on lines that are ADDED or MODIFIED (marked with `+`). Do not comment on removed or unchanged context lines.
3. Severity levels:
   - **critical**: Bugs, security vulnerabilities, data loss risks.
   - **warning**: Performance issues, error handling gaps, logic concerns.
   - **suggestion**: Better patterns, readability improvements.
   - **nitpick**: Style, naming, minor formatting.
4. Keep comments concise and actionable.
5. For `suggestion`, provide ONLY the replacement line(s) that would go inside a GitHub ```suggestion``` block. Omit this field if you have no concrete fix.
6. Do NOT invent issues. If the code looks correct, return an empty comments list.
7. Focus on substance: bugs, security, correctness, performance. Avoid stylistic nitpicks unless they hurt readability significantly.
"""


TRIAGE_SYSTEM_PROMPT = """\
You are a senior engineer triaging a large pull request. You will receive a list of changed files with their hunk headers (no code).

Respond with a JSON object:

```json
{{
  "files": [
    {{
      "file": "path/to/file.py",
      "risk": "high|medium|low",
      "reason": "Brief reason for the risk assessment."
    }}
  ],
  "summary": "Overall PR assessment."
}}
```

Mark files as "high" risk if they:
- Modify security-sensitive code (auth, crypto, permissions)
- Change core business logic
- Modify database schemas or queries
- Alter API contracts
- Have complex algorithmic changes

Mark as "low" risk:
- Auto-generated files, lock files, configs
- Test fixtures, snapshots
- Documentation-only changes
- Simple renames or moves

Be conservative: when in doubt, mark as medium.
"""


def annotate_diff_for_llm(files: list[DiffFile]) -> str:
    """Annotate diff files with line numbers for LLM consumption."""
    parts: list[str] = []

    for f in files:
        parts.append(f"### File: {f.path}")
        if f.is_rename:
            parts.append(f"(renamed from {f.source_file})")
        if f.is_binary:
            parts.append("(binary file)")
            continue

        for hunk in f.hunks:
            header = (
                f"@@ -{hunk.source_start},{hunk.source_length} "
                f"+{hunk.target_start},{hunk.target_length} @@ "
                f"{hunk.section_header}"
            )
            parts.append(header)

            for line in hunk.lines:
                if line.is_removed:
                    # Show source line number for removed lines
                    num = line.source_line_number or ""
                    parts.append(f" {num:>4} |- {line.content}")
                elif line.is_added:
                    num = line.target_line_number or ""
                    parts.append(f" {num:>4} |+ {line.content}")
                else:
                    num = line.target_line_number or ""
                    parts.append(f" {num:>4} |  {line.content}")

        parts.append("")

    return "\n".join(parts)


def build_review_prompt(
    files: list[DiffFile],
    all_files: list[DiffFile],
    rules: str | None = None,
    extra_instructions: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for a chunk review.

    Returns (system_prompt, user_prompt).
    """
    system = REVIEW_SYSTEM_PROMPT
    if rules:
        system += f"\n\n## Additional Review Rules\n\n{rules}"

    user_parts: list[str] = []

    # File manifest for cross-file awareness
    manifest = build_file_manifest(all_files)
    user_parts.append(manifest)
    user_parts.append("")

    if extra_instructions:
        user_parts.append(f"## Extra Instructions from PR Author\n{extra_instructions}")
        user_parts.append("")

    user_parts.append("## Diff to Review\n")
    user_parts.append(annotate_diff_for_llm(files))

    return system, "\n".join(user_parts)


def build_triage_prompt(
    files: list[DiffFile],
) -> tuple[str, str]:
    """Build system and user prompts for the triage pass.

    Returns (system_prompt, user_prompt).
    """
    parts: list[str] = ["## Changed Files\n"]

    for f in files:
        parts.append(f"### {f.path}")
        if f.is_binary:
            parts.append("  (binary file)")
            continue
        for hunk in f.hunks:
            header = (
                f"  @@ -{hunk.source_start},{hunk.source_length} "
                f"+{hunk.target_start},{hunk.target_length} @@ "
                f"{hunk.section_header}"
            )
            parts.append(header)
        parts.append("")

    return TRIAGE_SYSTEM_PROMPT, "\n".join(parts)
