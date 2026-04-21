"""Small shared helpers for ScorpionTrack."""

from __future__ import annotations


def mask_token(value: str, *, visible: int = 4) -> str:
    """Return a lightly redacted token for logging."""
    cleaned = value.strip()
    if not cleaned:
        return "<empty>"
    if len(cleaned) <= visible * 2:
        return "*" * len(cleaned)
    return f"{cleaned[:visible]}...{cleaned[-visible:]}"
