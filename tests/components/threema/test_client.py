"""Unit tests for the Threema Gateway API client wrapper.

`ThreemaAPIClient` only wires Home Assistant's shared aiohttp session into
`aiothreema.ThreemaGatewayClient`. The Gateway HTTP protocol, encryption,
and key generation are implemented and tested in that library itself, so
this file only tests the wiring this integration owns.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiothreema import ThreemaGatewayClient

from homeassistant.components.threema.client import ThreemaAPIClient
from homeassistant.core import HomeAssistant

from .conftest import MOCK_API_SECRET, MOCK_GATEWAY_ID, MOCK_PRIVATE_KEY


def _patch_session(session: MagicMock):
    """Return a context manager that patches async_get_clientsession."""
    return patch(
        "homeassistant.components.threema.client.async_get_clientsession",
        return_value=session,
    )


def test_is_a_threema_gateway_client(hass: HomeAssistant) -> None:
    """Test the wrapper is usable wherever a ThreemaGatewayClient is expected."""
    with _patch_session(MagicMock()):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
    assert isinstance(client, ThreemaGatewayClient)


def test_uses_home_assistants_shared_session(hass: HomeAssistant) -> None:
    """Test the client is wired to Home Assistant's shared aiohttp session."""
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.threema.client.async_get_clientsession",
        return_value=mock_session,
    ) as mock_get_session:
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)

    mock_get_session.assert_called_once_with(hass)
    assert client._session is mock_session


def test_passes_through_credentials(hass: HomeAssistant) -> None:
    """Test gateway id, API secret, and private key are passed through as-is."""
    with _patch_session(MagicMock()):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=MOCK_PRIVATE_KEY
        )
    assert client.gateway_id == MOCK_GATEWAY_ID
    assert client.api_secret == MOCK_API_SECRET
    assert client.private_key == MOCK_PRIVATE_KEY


def test_private_key_defaults_to_none(hass: HomeAssistant) -> None:
    """Test private_key defaults to None for simple (non-E2E) mode."""
    with _patch_session(MagicMock()):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
    assert client.private_key is None
