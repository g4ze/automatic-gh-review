from __future__ import annotations

from pydantic import BaseModel


class WebhookUser(BaseModel):
    login: str
    id: int


class WebhookIssue(BaseModel):
    number: int
    pull_request: dict | None = None


class WebhookComment(BaseModel):
    id: int
    body: str
    user: WebhookUser


class WebhookRepo(BaseModel):
    full_name: str

    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0]

    @property
    def name(self) -> str:
        return self.full_name.split("/")[1]


class IssueCommentEvent(BaseModel):
    action: str
    issue: WebhookIssue
    comment: WebhookComment
    repository: WebhookRepo
