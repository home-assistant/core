"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import RAIN_SENSOR_OFF, RAIN_SENSOR_ON, SERIAL_NUMBER

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await config_entry.async_setup(hass)
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("rain_response", "expected_state"),
    [(RAIN_SENSOR_OFF, "off"), (RAIN_SENSOR_ON, "on")],
)
async def test_rainsensor(
    hass: HomeAssistant,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    expected_state: bool,
) -> None:
    """Test rainsensor binary sensor."""

    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert rainsensor.state == expected_state
    assert rainsensor.attributes == {
        "friendly_name": "Rain Bird Controller Rainsensor",
        "icon": "mdi:water",
    }


@pytest.mark.parametrize(
    ("config_entry_unique_id", "entity_unique_id"),
    [
        (SERIAL_NUMBER, "1263613994342-rainsensor"),
        # Some existing config entries may have a "0" serial number but preserve
        # their unique id
        (0, "0-rainsensor"),
    ],
)
async def test_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_unique_id: str,
) -> None:
    """Test rainsensor binary sensor."""
    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert rainsensor.attributes == {
        "friendly_name": "Rain Bird Controller Rainsensor",
        "icon": "mdi:water",
    }

    entity_entry = entity_registry.async_get(
        "binary_sensor.rain_bird_controller_rainsensor"
    )
    assert entity_entry
    assert entity_entry.unique_id == entity_unique_id


@pytest.mark.parametrize(
    ("config_entry_unique_id"),
    [
        (None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test rainsensor binary sensor with no unique id."""

    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert (
        rainsensor.attributes.get("friendly_name") == "Rain Bird Controller Rainsensor"
    )

    entity_entry = entity_registry.async_get(
        "binary_sensor.rain_bird_controller_rainsensor"
    )
    assert not entity_entry
