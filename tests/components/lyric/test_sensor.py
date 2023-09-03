"""Test the Honeywell Lyric sensor platform."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_room_accessories_temperature_sensors(hass: HomeAssistant) -> None:
    """Temperature sensors should be created for each room accessory in data."""
    await init_integration(hass, Platform.SENSOR)

    state = hass.states.get("sensor.family_room_average_temperature")
    assert state is not None
    assert state.state == "76.2"

    state = hass.states.get("sensor.hallway_average_temperature")
    assert state is not None
    assert state.state == "72.5"

    state = hass.states.get("sensor.library_average_temperature")
    assert state is not None
    assert state.state == "71"

    state = hass.states.get("sensor.living_room_average_temperature")
    assert state is not None
    assert state.state == "79"

    state = hass.states.get("sensor.master_bedroom_average_temperature")
    assert state is not None
    assert state.state == "73.12"

    state = hass.states.get("sensor.office_average_temperature")
    assert state is not None
    assert state.state == "76"


async def test_room_accessories_humidity_sensors(hass: HomeAssistant) -> None:
    """Humidity sensors should be created for each room accessory in data."""
    await init_integration(hass, Platform.SENSOR)

    state = hass.states.get("sensor.family_room_average_humidity")
    assert state is not None
    assert state.state == "61"

    state = hass.states.get("sensor.hallway_average_humidity")
    assert state is not None
    assert state.state == "59"

    state = hass.states.get("sensor.library_average_humidity")
    assert state is not None
    assert state.state == "65"

    state = hass.states.get("sensor.living_room_average_humidity")
    assert state is not None
    assert state.state == "63"

    state = hass.states.get("sensor.master_bedroom_average_humidity")
    assert state is not None
    assert state.state == "58"

    state = hass.states.get("sensor.office_average_humidity")
    assert state is not None
    assert state.state == "57"
