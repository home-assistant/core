"""Tests for Kii Audio config flow helpers."""

import pytest

from homeassistant.components.kii_audio.config_flow import (
    _decode_property,
    _supports_plain_websocket_backend,
)


def test_decode_property() -> None:
    """Test decoding zeroconf TXT properties."""
    assert _decode_property(None) is None
    assert _decode_property(b"hello") == "hello"
    assert _decode_property("hello") == "hello"
    assert _decode_property(123) == "123"


@pytest.mark.parametrize("version", [2, 2.0, "2", "2.1"])
def test_supports_plain_websocket_backend(version: float | str) -> None:
    """Test supported backend versions are accepted."""
    assert _supports_plain_websocket_backend({"version": version}) is True


@pytest.mark.parametrize("version", [None, True, 1, 1.0, "1", "old", ""])
def test_supports_plain_websocket_backend_rejects_legacy_or_invalid(
    version: object,
) -> None:
    """Test legacy or invalid backend versions are rejected."""
    assert _supports_plain_websocket_backend({"version": version}) is False


def test_supports_plain_websocket_backend_requires_version() -> None:
    """Test backend support requires an advertised version."""
    assert _supports_plain_websocket_backend({}) is False
