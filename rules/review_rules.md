# Review Rules

## Priorities

1. **Security**: Flag any hardcoded secrets, SQL injection, XSS, command injection, or insecure deserialization.
2. **Correctness**: Look for logic errors, off-by-one errors, null pointer dereferences, race conditions.
3. **Error handling**: Ensure exceptions are properly caught and not silently swallowed.
4. **Performance**: Flag obvious N+1 queries, unbounded loops, or missing pagination.

## Style Guidelines

- Prefer early returns over deeply nested conditionals.
- Functions should do one thing.
- Avoid magic numbers; use named constants.

## What NOT to Comment On

- Import ordering (handled by tooling).
- Line length (handled by formatter).
- Trailing whitespace or formatting issues.
- Minor naming preferences unless genuinely confusing.
