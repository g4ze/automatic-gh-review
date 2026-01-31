from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.dependencies import HttpClientDep, SettingsDep
from app.webhook.models import IssueCommentEvent
from app.webhook.signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def health() -> dict:
    """Health check endpoint for monitoring."""
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    http_client: HttpClientDep,
    x_hub_signature_256: str = Header(""),
    x_github_event: str = Header(""),
) -> dict:
    body = await request.body()

    # 1. Verify signature (always against the raw body bytes)
    if not verify_signature(body, settings.github_webhook_secret, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Only handle issue_comment events
    if x_github_event != "issue_comment":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    # 3. Extract JSON — GitHub sends either raw JSON (application/json)
    #    or form-encoded with a `payload` field (application/x-www-form-urlencoded)
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = parse_qs(body.decode())
        payload_values = form.get("payload")
        if not payload_values:
            raise HTTPException(status_code=400, detail="Missing payload field")
        json_bytes = payload_values[0].encode()
    else:
        json_bytes = body

    event = IssueCommentEvent.model_validate_json(json_bytes)

    # 3. Gate checks
    if event.action != "created":
        return {"status": "ignored", "reason": f"action={event.action}"}

    if event.issue.pull_request is None:
        return {"status": "ignored", "reason": "not a PR comment"}

    trigger = settings.trigger_phrase.lower()
    comment_body = event.comment.body.lower()
    if trigger not in comment_body:
        return {"status": "ignored", "reason": "no trigger phrase"}

    # 4. Extract extra instructions (everything after the trigger phrase)
    idx = comment_body.index(trigger) + len(trigger)
    extra_instructions = event.comment.body[idx:].strip()

    logger.info(
        "Trigger detected on %s#%d by %s",
        event.repository.full_name,
        event.issue.number,
        event.comment.user.login,
    )

    # 5. Dispatch background review task
    from app.review.orchestrator import run_review  # noqa: E402

    background_tasks.add_task(
        run_review,
        settings=settings,
        http_client=http_client,
        owner=event.repository.owner,
        repo=event.repository.name,
        pr_number=event.issue.number,
        extra_instructions=extra_instructions,
    )

    return {"status": "processing"}
