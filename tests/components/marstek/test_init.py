"""Tests for the Marstek integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_ES_MODE_RESPONSE, create_mock_udp_client

from tests.common import MockConfigEntry


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the async_setup function."""
    result = await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert result is True
    # Services are not registered in this version
    assert not hass.services.has_service(DOMAIN, "charge")
    assert not hass.services.has_service(DOMAIN, "discharge")
    assert not hass.services.has_service(DOMAIN, "stop")


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    # Override send_request to return immediately
    async def mock_send_request(message, *args, **kwargs):
        try:
            msg = json.loads(message)
            if msg.get("method") == "ES.GetMode":
                return MOCK_ES_MODE_RESPONSE
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass
        return MOCK_ES_MODE_RESPONSE

    mock_client.send_request = AsyncMock(side_effect=mock_send_request)
    # Prevent listen task from being created
    mock_client._listen_task = None

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        # Verify runtime_data is set
        assert mock_config_entry.runtime_data is not None


async def test_services_not_available(hass: HomeAssistant) -> None:
    """Validate removed services are not registered."""
    mock_client = create_mock_udp_client()

    with patch("pymarstek.MarstekUDPClient", return_value=mock_client):
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert result is True
        assert not hass.services.has_service(DOMAIN, "charge")
        assert not hass.services.has_service(DOMAIN, "discharge")
        assert not hass.services.has_service(DOMAIN, "stop")
