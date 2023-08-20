"""The tests for the demo weather component."""
import datetime
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import weather
from homeassistant.components.demo.weather import WEATHER_UPDATE_INTERVAL
from homeassistant.components.weather import (
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

from tests.typing import WebSocketGenerator


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


TEST_TIME_ADVANCE_INTERVAL = datetime.timedelta(seconds=5 + 1)


@pytest.mark.parametrize(
    ("forecast_type", "expected_forecast"),
    [
        (
            "daily",
            [
                {
                    "condition": "snowy",
                    "precipitation": 2.0,
                    "temperature": -23.3,
                    "templow": -26.1,
                    "precipitation_probability": 60,
                },
                {
                    "condition": "sunny",
                    "precipitation": 0.0,
                    "temperature": -22.8,
                    "templow": -24.4,
                    "precipitation_probability": 0,
                },
            ],
        ),
        (
            "hourly",
            [
                {
                    "condition": "sunny",
                    "precipitation": 2.0,
                    "temperature": -23.3,
                    "templow": -26.1,
                    "precipitation_probability": 60,
                },
                {
                    "condition": "sunny",
                    "precipitation": 0.0,
                    "temperature": -22.8,
                    "templow": -24.4,
                    "precipitation_probability": 0,
                },
            ],
        ),
        (
            "twice_daily",
            [
                {
                    "condition": "snowy",
                    "precipitation": 2.0,
                    "temperature": -23.3,
                    "templow": -26.1,
                    "precipitation_probability": 60,
                },
                {
                    "condition": "sunny",
                    "precipitation": 0.0,
                    "temperature": -22.8,
                    "templow": -24.4,
                    "precipitation_probability": 0,
                },
            ],
        ),
    ],
)
async def test_forecast(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    disable_platforms: None,
    forecast_type: str,
    expected_forecast: list[dict[str, Any]],
) -> None:
    """Test multiple forecast."""
    assert await async_setup_component(
        hass, weather.DOMAIN, {"weather": {"platform": "demo"}}
    )
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": forecast_type,
            "entity_id": "weather.demo_weather_north",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast1 = msg["event"]["forecast"]

    assert len(forecast1) == 7
    for key, val in expected_forecast[0].items():
        assert forecast1[0][key] == val
    for key, val in expected_forecast[1].items():
        assert forecast1[6][key] == val

    freezer.tick(WEATHER_UPDATE_INTERVAL + datetime.timedelta(seconds=1))
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 != forecast1
    assert len(forecast2) == 7
