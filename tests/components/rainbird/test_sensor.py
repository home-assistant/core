"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import RAIN_DELAY, ComponentSetup, mock_response

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test sensor platform."""

    responses.append(mock_response(RAIN_DELAY))

    assert await setup_integration()

    raindelay = hass.states.get("sensor.raindelay")
    assert raindelay is not None
    assert raindelay.state == "16"
    assert raindelay.attributes == {
        "friendly_name": "Raindelay",
        "icon": "mdi:water-off",
    }
