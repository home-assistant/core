"""Test the ThermoPro config flow."""
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TP357_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp357_2142_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "24.1"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp357_2142_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Battery"
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
