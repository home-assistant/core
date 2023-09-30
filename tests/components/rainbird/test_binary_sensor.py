"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CONFIG_ENTRY_DATA, RAIN_SENSOR_OFF, RAIN_SENSOR_ON, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.parametrize(
    ("rain_response", "expected_state"),
    [(RAIN_SENSOR_OFF, "off"), (RAIN_SENSOR_ON, "on")],
)
async def test_rainsensor(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    expected_state: bool,
) -> None:
    """Test rainsensor binary sensor."""

    assert await setup_integration()

    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert rainsensor.state == expected_state
    assert rainsensor.attributes == {
        "friendly_name": "Rain Bird Controller Rainsensor",
        "icon": "mdi:water",
    }

    entity = entity_registry.async_get("binary_sensor.rain_bird_controller_rainsensor")
    assert entity
    assert entity.unique_id == "1263613994342-rainsensor"


@pytest.mark.parametrize(
    ("config_entry_data"),
    [
        ({**CONFIG_ENTRY_DATA, "serial_number": 0}),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test rainsensor binary sensor with no unique id."""

    assert await setup_integration()

    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert (
        rainsensor.attributes.get("friendly_name") == "Rain Bird Controller Rainsensor"
    )

    entity = entity_registry.async_get("binary_sensor.rain_bird_controller_rainsensor")
    assert not entity
