"""Shared synthetic OAuth helpers for NuHeat tests."""

import base64
import json


def jwt_access_token(
    subject: str | None = "synthetic-account-subject", *, marker: str | None = None
) -> str:
    """Create a clearly synthetic unsigned JWT for identity-claim tests."""

    def encode(value: dict[str, str]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    payload: dict[str, str] = {}
    if subject is not None:
        payload["sub"] = subject
    if marker is not None:
        payload["test_marker"] = marker
    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.synthetic"
