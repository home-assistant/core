"""The test for weather entity."""
import pytest
from pytest import approx

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_WEATHER_TEMPERATURE,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM


@pytest.mark.parametrize(
    "unit_system,native_unit,state_unit,native_value,state_value",
    [
        (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT, TEMP_FAHRENHEIT, 100, 100),
        (IMPERIAL_SYSTEM, TEMP_CELSIUS, TEMP_FAHRENHEIT, 37.8, 100),
        (METRIC_SYSTEM, TEMP_FAHRENHEIT, TEMP_CELSIUS, 100, 37.8),
        (METRIC_SYSTEM, TEMP_CELSIUS, TEMP_CELSIUS, 37.8, 37.8),
    ],
)
async def test_temperature_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    state_unit,
    native_value,
    state_value,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            native_temperature=native_value,
            native_temperature_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        float(state_value)
    )
