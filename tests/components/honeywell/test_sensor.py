"""Test honeywell sensor."""
from aiosomecomfort.device import Device
from aiosomecomfort.location import Location
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(("unit", "temp"), [("C", "5"), ("F", "-15")])
async def test_outdoor_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    location: Location,
    device_with_outdoor_sensor: Device,
    unit,
    temp,
) -> None:
    """Test outdoor temperature sensor."""
    device_with_outdoor_sensor.temperature_unit = unit
    location.devices_by_id[
        device_with_outdoor_sensor.deviceid
    ] = device_with_outdoor_sensor
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    temperature_state = hass.states.get("sensor.device3_outdoor_temperature")
    humidity_state = hass.states.get("sensor.device3_outdoor_humidity")

    assert temperature_state
    assert humidity_state
    assert temperature_state.state == temp
    assert humidity_state.state == "25"


@pytest.mark.parametrize(("unit", "temp"), [("C", "5"), ("F", "-15")])
async def test_indoor_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    location: Location,
    device_with_indoor_sensors_only: Device,
    unit,
    temp,
) -> None:
    """Test indoor temperature sensor with no outdoor sensors."""
    device_with_indoor_sensors_only.temperature_unit = unit
    device_with_indoor_sensors_only.current_temperature = 5
    device_with_indoor_sensors_only.current_humidity = 25
    location.devices_by_id[
        device_with_indoor_sensors_only.deviceid
    ] = device_with_indoor_sensors_only
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.device4_outdoor_temperature") is None
    assert hass.states.get("sensor.device4_outdoor_humidity") is None

    temperature_state = hass.states.get("sensor.device4_temperature")
    humidity_state = hass.states.get("sensor.device4_humidity")

    assert temperature_state
    assert humidity_state
    assert temperature_state.state == temp
    assert humidity_state.state == "25"
