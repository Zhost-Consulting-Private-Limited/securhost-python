"""
Verifying a webhook the gateway sent.

Shipped because the alternative is every integrator writing this themselves,
and the two mistakes that make a signature check worthless are both easy to
make and invisible when you do:

**Comparing with `==`.** String equality returns as soon as it finds a
differing byte, so how long it takes leaks how much of the prefix was right.
That is enough to recover a signature a byte at a time. `compare_digest` takes
the same time whatever the input.

**Signing the body without the timestamp inside the MAC.** If the timestamp is
merely sent alongside, an attacker replays yesterday's payload with today's
timestamp and the signature still verifies. It is inside the message here, and
`tolerance_seconds` is what turns that into an actual replay window.

The scheme mirrors `securhost/domain/webhooks/services.py` exactly: HMAC-SHA256,
hex-encoded, over `timestamp.body`.
"""

from __future__ import annotations

import hashlib
import hmac
import time

#: How far out of date a signed payload may be. Five minutes covers a
#: retry and a slow queue without leaving a captured request replayable for
#: an afternoon.
DEFAULT_TOLERANCE_SECONDS = 300


def verify_signature(
    *,
    secret: str,
    body: str | bytes,
    timestamp: str,
    signature: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Whether this payload really came from the gateway, recently.

    `body` must be the **raw** request body, exactly as received. Re-encoding
    a parsed dict changes key order and whitespace and the signature will not
    match — which is the single most common reason this returns False for a
    genuine delivery.
    """
    if not secret or not signature or not timestamp:
        return False

    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")

    try:
        sent_at = float(timestamp)
    except (TypeError, ValueError):
        return False

    if tolerance_seconds and abs(time.time() - sent_at) > tolerance_seconds:
        return False

    expected = hmac.new(
        secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


__all__ = ["DEFAULT_TOLERANCE_SECONDS", "verify_signature"]
