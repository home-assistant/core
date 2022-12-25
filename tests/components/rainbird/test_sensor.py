"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import (
    RAIN_DELAY,
    RAIN_SENSOR_OFF,
    RAIN_SENSOR_ON,
    ComponentSetup,
    mock_response,
)

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.parametrize(
    "sensor_payload,expected_state",
    [(RAIN_SENSOR_OFF, "False"), (RAIN_SENSOR_ON, "True")],
)
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    sensor_payload: str,
    expected_state: bool,
) -> None:
    """Test sensor platform."""

    responses.extend([mock_response(sensor_payload), mock_response(RAIN_DELAY)])

    assert await setup_integration()

    rainsensor = hass.states.get("sensor.rainsensor")
    assert rainsensor is not None
    assert rainsensor.state == expected_state

    raindelay = hass.states.get("sensor.raindelay")
    assert raindelay is not None
    assert raindelay.state == "16"
