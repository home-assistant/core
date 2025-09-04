"""Tests for the Aladdin Connect integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
            }
        },
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    mock_door = AsyncMock()
    mock_door.device_id = "test_device_id"
    mock_door.door_number = 1
    mock_door.name = "Test Door"
    mock_door.status = "closed"
    mock_door.link_status = "connected"
    mock_door.battery_level = 100

    mock_client = AsyncMock()
    mock_client.get_doors.return_value = [mock_door]

    with (
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.OAuth2Session",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.AladdinConnectClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.aladdin_connect.api.AsyncConfigEntryAuth",
            return_value=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test a successful unload entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
            }
        },
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    # Mock door data
    mock_door = AsyncMock()
    mock_door.device_id = "test_device_id"
    mock_door.door_number = 1
    mock_door.name = "Test Door"
    mock_door.status = "closed"
    mock_door.link_status = "connected"
    mock_door.battery_level = 100

    # Mock client
    mock_client = AsyncMock()
    mock_client.get_doors.return_value = [mock_door]

    with (
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.OAuth2Session",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.AladdinConnectClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.aladdin_connect.api.AsyncConfigEntryAuth",
            return_value=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
