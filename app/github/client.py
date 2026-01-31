from __future__ import annotations

import logging

import httpx

from app.github.models import PRDetails, ReviewSubmission

logger = logging.getLogger(__name__)

BASE_URL = "https://api.github.com"


async def get_pr_details(
    client: httpx.AsyncClient, owner: str, repo: str, pr_number: int
) -> PRDetails:
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    resp = await client.get(url)
    resp.raise_for_status()
    return PRDetails.from_api(resp.json())


async def get_pr_diff(
    client: httpx.AsyncClient, owner: str, repo: str, pr_number: int
) -> str:
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    resp = await client.get(
        url, headers={"Accept": "application/vnd.github.v3.diff"}
    )
    resp.raise_for_status()
    return resp.text


async def get_file_content(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> str | None:
    """Fetch a file from the repo. Returns None if not found."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/contents/{path}"
    resp = await client.get(
        url,
        params={"ref": ref},
        headers={"Accept": "application/vnd.github.v3.raw"},
    )
    if resp.status_code == 404:
        logger.debug("File not found: %s@%s", path, ref)
        return None
    resp.raise_for_status()
    return resp.text


async def post_review(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    review: ReviewSubmission,
) -> dict:
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    payload = review.model_dump()
    logger.info(
        "Posting review on %s/%s#%d: event=%s, %d comments",
        owner,
        repo,
        pr_number,
        review.event,
        len(review.comments),
    )
    resp = await client.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


async def post_reaction(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    comment_id: int,
    reaction: str = "eyes",
) -> None:
    """Add a reaction to a comment to acknowledge processing."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions"
    resp = await client.post(url, json={"content": reaction})
    if resp.status_code not in (200, 201):
        logger.warning("Failed to add reaction: %s", resp.text)
