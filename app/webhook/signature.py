from __future__ import annotations

import hashlib
import hmac


def verify_signature(payload: bytes, secret: str, signature_header: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature.

    Args:
        payload: Raw request body bytes.
        secret: The webhook secret configured on GitHub.
        signature_header: Value of the X-Hub-Signature-256 header
                          (e.g. "sha256=abc123...").

    Returns:
        True if the signature is valid.
    """
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
