"""Test the Tilt Hydrometer BLE sensors."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothCallback, BluetoothChange
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.tilt_ble.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TILT_GREEN_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    saved_callback: BluetoothCallback | None = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert saved_callback is not None
    saved_callback(TILT_GREEN_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    temp_sensor = hass.states.get("sensor.tilt_green_temperature")
    assert temp_sensor is not None

    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "21"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Tilt Green Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tilt_green_specific_gravity")
    assert temp_sensor is not None

    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "1.003"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Tilt Green Specific Gravity"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
