"""Tests for AEMET OpenData utilities."""

import base64
from datetime import UTC, datetime
import json
from typing import Any

import pytest

from homeassistant.components.aemet.util import get_api_key_expiration


def _create_api_key(payload: Any) -> str:
    """Create a fake JWT with the given payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    encoded_payload = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"{header}.{encoded_payload}.signature"


def test_get_api_key_expiration() -> None:
    """Test reading the expiration from an API key."""
    expiration = datetime(2026, 1, 1, tzinfo=UTC)
    api_key = _create_api_key({"iat": 1764547200, "exp": expiration.timestamp()})

    assert get_api_key_expiration(api_key) == expiration


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"iat": 1764547200},
        {"exp": "1767225600"},
        {"exp": True},
        {"exp": None},
        {"exp": 1e30},
        [],
    ],
)
def test_get_api_key_expiration_without_valid_expiration(payload: Any) -> None:
    """Test reading an API key without a valid expiration claim."""
    assert get_api_key_expiration(_create_api_key(payload)) is None


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        "not-a-jwt",
        "header.payload",
        "header.%%%.signature",
        "header.e30.signature",
    ],
)
def test_get_api_key_expiration_with_invalid_jwt(api_key: str) -> None:
    """Test reading an invalid API key."""
    assert get_api_key_expiration(api_key) is None
