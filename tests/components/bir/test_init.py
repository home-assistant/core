"""Tests for the BIR integration."""

from unittest.mock import AsyncMock, patch

from pybirno import BirConnectionError
import pytest

from homeassistant.components.bir.const import CONF_PROPERTY_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_bir_client")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BIR configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BIR configuration entry not ready."""
    with patch(
        "homeassistant.components.bir.coordinator.BirClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_pickups = AsyncMock(
            side_effect=BirConnectionError("Connection failed")
        )
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_bir_client")
async def test_remove_stale_devices_after_reconfigure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that stale devices from a previous address are removed on setup."""
    mock_config_entry.add_to_hass(hass)

    # Create a stale device with a different property_id (simulating a previous address)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "old_property_id")},
        name="Old Address, Bergen",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Stale device should be removed
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, "old_property_id")}
    )

    # Current device should exist
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.data[CONF_PROPERTY_ID])}
    )
