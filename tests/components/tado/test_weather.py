"""The weather tests for the tado platform."""

from homeassistant.components.tado.const import ATTRIBUTION
from homeassistant.components.weather import (
    ATTR_CONDITION_FOG,
    ATTR_WEATHER_TEMPERATURE,
)
from homeassistant.const import ATTR_ATTRIBUTION

from .util import async_init_integration


async def test_weather(hass):
    """Test states of the weather without forecast."""

    await async_init_integration(hass)

    state = hass.states.get("weather.home_name")
    assert state
    assert state.state == ATTR_CONDITION_FOG
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == 7.5
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
