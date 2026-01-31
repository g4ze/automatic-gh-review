from __future__ import annotations

from fnmatch import fnmatch

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required
    github_webhook_secret: str
    github_token: str

    gemini_api_key: str

    # LLM
    litellm_model: str 
    litellm_max_tokens: int = 4096
    litellm_temperature: float = 0.2

    # Trigger
    trigger_phrase: str = "pls review my code gpt gods"

    # Review rules
    review_rules_path: str = "rules/review_rules.md"

    # Diff / chunking
    max_diff_tokens_per_chunk: int = 6000
    max_total_diff_tokens: int = 100_000
    max_concurrent_chunks: int = 3

    # Review limits
    max_comments_per_review: int = 30
    max_files_deep_review: int = 15

    # File ignore patterns (comma-separated globs)
    ignore_patterns: str | list[str] = [
        "*.lock",
        "*.min.js",
        "*.min.css",
        "*.generated.*",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ]

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_parse_none_str": "null",
    }

    @field_validator("ignore_patterns", mode="before")
    @classmethod
    def parse_ignore_patterns(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return v
        return []

    def should_ignore_file(self, path: str) -> bool:
        filename = path.rsplit("/", 1)[-1]
        return any(fnmatch(filename, pat) for pat in self.ignore_patterns)
