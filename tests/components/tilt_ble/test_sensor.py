"""Test the Tilt Hydrometer BLE sensors."""

from __future__ import annotations

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.tilt_ble.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TILT_GREEN_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="F6:0F:28:F2:1F:CB",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TILT_GREEN_SERVICE_INFO)
    await hass.async_block_till_done()
    assert (
        len(hass.states.async_all()) >= 2
    )  # may trigger ibeacon integration as well since tilt uses ibeacon

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
