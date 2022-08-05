"""Test the SensorPush config flow."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.sensorpush.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

from . import HTPWX_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    saved_callback = None

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
    saved_callback(HTPWX_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.htp_xw_f4d_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "20.11"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "HTP.xw F4D Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
