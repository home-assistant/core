"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import RAIN_SENSOR_OFF, RAIN_SENSOR_ON, ComponentSetup, mock_response

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.parametrize(
    "sensor_payload,expected_state",
    [(RAIN_SENSOR_OFF, "off"), (RAIN_SENSOR_ON, "on")],
)
async def test_rainsensor(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    sensor_payload: str,
    expected_state: bool,
) -> None:
    """Test rainsensor binary sensor."""

    responses.append(mock_response(sensor_payload))

    assert await setup_integration()

    rainsensor = hass.states.get("binary_sensor.rainsensor")
    assert rainsensor is not None
    assert rainsensor.state == expected_state
    assert rainsensor.attributes == {
        "friendly_name": "Rainsensor",
        "icon": "mdi:water",
    }
