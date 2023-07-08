"""The tests for the demo weather component."""
from homeassistant.components import weather
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM


async def test_attributes(hass: HomeAssistant, disable_platforms) -> None:
    """Test weather attributes."""
    assert await async_setup_component(
        hass, weather.DOMAIN, {"weather": {"platform": "demo"}}
    )
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    state = hass.states.get("weather.demo_weather_south")
    assert state is not None

    assert state.state == "sunny"

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) == 21.6
    assert data.get(ATTR_WEATHER_HUMIDITY) == 92
    assert data.get(ATTR_WEATHER_PRESSURE) == 1099
    assert data.get(ATTR_WEATHER_WIND_SPEED) == 1.8  # 0.5 m/s -> km/h
    assert data.get(ATTR_WEATHER_WIND_BEARING) is None
    assert data.get(ATTR_WEATHER_OZONE) is None
    assert data.get(ATTR_ATTRIBUTION) == "Powered by Home Assistant"
    assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_CONDITION) == "rainy"
    assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_PRECIPITATION) == 1
    assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 60
    assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_TEMP) == 22
    assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_TEMP_LOW) == 15
    assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_CONDITION) == "fog"
    assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_PRECIPITATION) == 0.2
    assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_TEMP) == 21
    assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_TEMP_LOW) == 12
    assert (
        data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 100
    )
    assert len(data.get(ATTR_FORECAST)) == 7
