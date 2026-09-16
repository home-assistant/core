"""Test the Eurotronic Comet WiFi integration setup."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import ENTITY_ID
from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mqtt_mock", "device")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test entry loads when thermostat answers, and unloads."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mqtt_mock")
async def test_setup_no_reply(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, device: FakeDevice
) -> None:
    """Test entry retries when the thermostat does not answer."""
    device.online = False
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_mqtt_not_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test entry retries when MQTT integration is not set up."""
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
