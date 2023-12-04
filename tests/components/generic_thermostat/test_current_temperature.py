"""Test the Generic Thermostat current temperature propagation from temperature sensor."""
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.generic_thermostat.const import ENT_SWITCH, ENTITY
from tests.components.generic_thermostat.shared import _setup_sensor


async def test_sensor_bad_value(hass: HomeAssistant, setup_comp_2) -> None:
    """Test sensor that have None as state."""
    state = hass.states.get(ENTITY)
    temp = state.attributes.get("current_temperature")

    _setup_sensor(hass, None)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("current_temperature") == temp

    _setup_sensor(hass, "inf")
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("current_temperature") == temp

    _setup_sensor(hass, "nan")
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("current_temperature") == temp


async def test_sensor_unknown(hass: HomeAssistant) -> None:
    """Test when target sensor is Unknown."""
    hass.states.async_set("sensor.unknown", STATE_UNKNOWN)
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "unknown",
                "heater": ENT_SWITCH,
                "target_sensor": "sensor.unknown",
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.unknown")
    assert state.attributes.get("current_temperature") is None


async def test_sensor_unavailable(hass: HomeAssistant) -> None:
    """Test when target sensor is Unavailable."""
    hass.states.async_set("sensor.unavailable", STATE_UNAVAILABLE)
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "unavailable",
                "heater": ENT_SWITCH,
                "target_sensor": "sensor.unavailable",
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.unavailable")
    assert state.attributes.get("current_temperature") is None
