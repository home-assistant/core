"""Tests for Kii Audio config flow helpers."""

import pytest

from homeassistant.components.kii_audio.config_flow import (
    _supports_plain_websocket_backend,
)


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
