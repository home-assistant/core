"""Test init of IronOS integration."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pynecil import CommunicationError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_pynecil", "ble_device")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("ble_device")
async def test_update_data_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test config entry not ready."""
    mock_pynecil.get_live_data.side_effect = CommunicationError
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_setup_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test config entry not ready."""
    mock_pynecil.get_settings.side_effect = CommunicationError
    mock_pynecil.get_device_info.side_effect = CommunicationError
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_settings_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test skipping of settings on exception."""
    mock_pynecil.get_settings.side_effect = CommunicationError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, datetime.now() + timedelta(seconds=60))
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("number.pinecil_boost_temperature"))
    assert state.state == STATE_UNKNOWN
