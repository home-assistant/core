"""Sensor entity tests for the WeatherKit integration."""

from typing import Any

import pytest

from homeassistant.core import HomeAssistant

from . import init_integration


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
    await init_integration(hass)

    state = hass.states.get(entity_name)
    assert state
    assert state.state == str(expected_value)
