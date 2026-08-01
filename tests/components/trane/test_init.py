"""Tests for the Trane Local integration setup."""

from unittest.mock import MagicMock

import pytest
from steamloop import AuthenticationError, SteamloopConnectionError

from homeassistant.components.trane.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_ENTRY_ID

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_zone_device_via_device_id(
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the zone device links to the thermostat device via via_device_id."""
    thermostat_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_ENTRY_ID), MOCK_ENTRY_ID
    )
    assert thermostat_device is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_ENTRY_ID}_1"), MOCK_ENTRY_ID
    )
    assert zone_device is not None
    assert zone_device.via_device_id == thermostat_device.id


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup retries on connection error."""
    mock_connection.connect.side_effect = SteamloopConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup fails on authentication error."""
    mock_connection.login.side_effect = AuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup retries on timeout."""
    mock_connection.connect.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
