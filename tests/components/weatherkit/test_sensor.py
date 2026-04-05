"""Sensor entity tests for the WeatherKit integration."""

from typing import Any

import pytest

from homeassistant.core import HomeAssistant

from . import init_integration, mock_weather_response


@pytest.mark.parametrize(
    ("entity_name", "expected_value"),
    [
        ("sensor.home_precipitation_intensity", 0.7),
        ("sensor.home_pressure_trend", "rising"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant, entity_name: str, expected_value: Any
) -> None:
    """Test that various sensor values match what we expect."""
    with mock_weather_response():
        await init_integration(hass)

    state = hass.states.get(entity_name)
    assert state
    assert state.state == str(expected_value)


async def test_alert_sensor(hass: HomeAssistant) -> None:
    """Test that the weather alert sensor returns the correct count and attributes."""
    hass.config.country = "US"
    with mock_weather_response():
        await init_integration(hass)

    state = hass.states.get("sensor.home_weather_alerts")
    assert state
    assert state.state == "2"

    assert state.attributes["alert_1"] == "Flood Watch"
    assert state.attributes["alert_severity_1"] == "moderate"
    assert state.attributes["alert_source_1"] == "National Weather Service"
    assert state.attributes["alert_time_1"] == "2023-09-08T18:00:00Z"
    assert state.attributes["alert_expiry_1"] == "2023-09-09T06:00:00Z"

    assert state.attributes["alert_2"] == "Wind Advisory"
    assert state.attributes["alert_severity_2"] == "minor"


async def test_alert_sensor_no_alerts(hass: HomeAssistant) -> None:
    """Test the weather alert sensor when alerts are not available."""
    hass.config.country = "US"
    with mock_weather_response(has_weather_alerts=False):
        await init_integration(hass)

    state = hass.states.get("sensor.home_weather_alerts")
    assert state is None
