from __future__ import annotations

from pydantic import BaseModel


class PRDetails(BaseModel):
    number: int
    title: str
    body: str | None = None
    head_sha: str
    base_ref: str
    head_ref: str
    default_branch: str

    @classmethod
    def from_api(cls, data: dict) -> PRDetails:
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            head_sha=data["head"]["sha"],
            base_ref=data["base"]["ref"],
            head_ref=data["head"]["ref"],
            default_branch=data["base"]["repo"]["default_branch"],
        )


class ReviewComment(BaseModel):
    path: str
    line: int
    side: str = "RIGHT"
    body: str


class ReviewSubmission(BaseModel):
    """Payload for POST /repos/{owner}/{repo}/pulls/{pr}/reviews."""

    commit_id: str
    body: str
    event: str  # "COMMENT" or "REQUEST_CHANGES"
    comments: list[ReviewComment]
