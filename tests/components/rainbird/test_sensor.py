"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import RAIN_DELAY, RAIN_DELAY_OFF, ComponentSetup


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    expected_state: str,
) -> None:
    """Test sensor platform."""

    assert await setup_integration()

    raindelay = hass.states.get("sensor.raindelay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Raindelay",
        "icon": "mdi:water-off",
    }
