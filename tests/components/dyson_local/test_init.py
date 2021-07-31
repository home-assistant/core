"""Tests for Dyson Local init."""
from unittest.mock import MagicMock, patch

from libdyson import DEVICE_TYPE_360_EYE, Dyson360Eye, VacuumEyePowerMode, VacuumState
from libdyson.exceptions import DysonConnectionRefused

from homeassistant.components.dyson_local import DOMAIN
from homeassistant.components.dyson_local.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_TYPE,
    CONF_SERIAL,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import CREDENTIAL, HOST, MODULE, NAME, SERIAL, get_base_device

from tests.common import MockConfigEntry

CONF_DATA = {
    CONF_SERIAL: SERIAL,
    CONF_CREDENTIAL: CREDENTIAL,
    CONF_HOST: HOST,
    CONF_DEVICE_TYPE: DEVICE_TYPE_360_EYE,
    CONF_NAME: NAME,
}


async def test_setup(hass: HomeAssistant):
    """Test setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_setup_entry(hass: HomeAssistant):
    """Test setup config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    config_entry.add_to_hass(hass)
    device = get_base_device(Dyson360Eye, DEVICE_TYPE_360_EYE)
    with patch(f"{MODULE}.get_device", return_value=device), patch(
        f"{MODULE}.binary_sensor.async_setup_entry"
    ) as mock_setup_binary_sensor, patch(
        f"{MODULE}.sensor.async_setup_entry"
    ) as mock_setup_sensor, patch(
        f"{MODULE}.vacuum.async_setup_entry"
    ) as mock_setup_vacuum:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    device.connect.assert_called_once_with(HOST)
    mock_setup_binary_sensor.assert_called_once()
    mock_setup_sensor.assert_called_once()
    mock_setup_vacuum.assert_called_once()


async def test_setup_entry_cannot_connect(hass: HomeAssistant):
    """Test setup config entry with connect failure."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    config_entry.add_to_hass(hass)
    device = get_base_device(Dyson360Eye, DEVICE_TYPE_360_EYE)
    type(device).connect = MagicMock(side_effect=DysonConnectionRefused)
    with patch(f"{MODULE}.get_device", return_value=device):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_unload(hass: HomeAssistant):
    """Test unload entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    config_entry.add_to_hass(hass)
    device = get_base_device(Dyson360Eye, DEVICE_TYPE_360_EYE)
    device.state = VacuumState.FULL_CLEAN_PAUSED
    device.battery_level = 50
    device.position = (10, 20)
    device.power_mode = VacuumEyePowerMode.QUIET
    device.battery_level = 80
    device.is_charging = False
    with patch(f"{MODULE}.get_device", return_value=device):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    hass.states.async_entity_ids_count() > 0
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    device.disconnect.assert_called_once_with()
    hass.states.async_entity_ids_count() == 0
