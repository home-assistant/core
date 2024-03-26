"""Test the ThermoPro config flow."""

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TP357_SERVICE_INFO, TP962R_SERVICE_INFO, TP962R_SERVICE_INFO_2

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_tp962r(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_2_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 2 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 6

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_1_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "82.0"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 1 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


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
