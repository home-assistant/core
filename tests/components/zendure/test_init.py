"""Integration setup tests for the Zendure integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from zendure import ZendureConnectionError, ZendureProtocolError

from homeassistant.components.zendure.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL_NUMBER


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zendure: MagicMock,
) -> None:
    """Test the Zendure configuration entry loading and unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_zendure.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_zendure")
@pytest.mark.parametrize("side_effect", [ZendureConnectionError, ZendureProtocolError])
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_read: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test the Zendure configuration entry not ready."""
    mock_read.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device(
    device_registry: dr.DeviceRegistry, init_integration: MockConfigEntry
) -> None:
    """Test the device is registered with its model and serial number."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), init_integration.entry_id
    )
    assert device
    assert device.manufacturer == "Zendure"
    assert device.model == "SolarFlow 2400 AC+"
    assert device.model_id == "solarFlow2400AC+"
    assert device.serial_number == SERIAL_NUMBER


@pytest.mark.parametrize("side_effect", [ZendureConnectionError, ZendureProtocolError])
async def test_device_unavailable_and_recovers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_read: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test entities become unavailable on a failed poll and then recover."""
    entity_id = "sensor.solarflow_2400_ac_battery"
    assert hass.states.get(entity_id).state == "57"

    mock_read.side_effect = side_effect
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_read.side_effect = None
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "57"
