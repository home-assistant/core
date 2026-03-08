"""Tests for Kaiterra API helpers."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.kaiterra.api_data import KaiterraApiClient


async def test_api_client_uses_library_default_base_url() -> None:
    """Test the wrapper does not override the library base URL."""
    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraAPIClient"
    ) as mock_client:
        KaiterraApiClient(object(), "test-api-key", "us")

    assert "base_url" not in mock_client.call_args.kwargs
    assert mock_client.call_args.kwargs["api_key"] == "test-api-key"
    assert mock_client.call_args.kwargs["aqi_standard"].value == "us"
