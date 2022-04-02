"""Test honeywell sensor."""
from somecomfort import Device, Location

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_outdoor_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    location: Location,
    device_with_outdoor_sensor: Device,
):
    """Test outdoor temperature sensor."""
    location.devices_by_id[
        device_with_outdoor_sensor.deviceid
    ] = device_with_outdoor_sensor
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    temperature_state = hass.states.get("sensor.device1_outdoor_temperature")
    humidity_state = hass.states.get("sensor.device1_outdoor_humidity")

    assert temperature_state
    assert humidity_state
    assert temperature_state.state == "5"
    assert humidity_state.state == "25"
