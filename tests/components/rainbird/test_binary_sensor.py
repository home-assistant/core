"""Tests for rainbird sensor platform."""

from http import HTTPStatus

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    RAIN_SENSOR_OFF,
    RAIN_SENSOR_ON,
    mock_response_error,
)

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
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


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
    }


@pytest.mark.parametrize(
    ("config_entry_data", "config_entry_unique_id", "setup_config_entry"),
    [
        (CONFIG_ENTRY_DATA_OLD_FORMAT, None, None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test rainsensor binary sensor with no unique id."""

    # Failure to migrate config entry to a unique id
    responses.insert(0, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    rainsensor = hass.states.get("binary_sensor.rain_bird_controller_rainsensor")
    assert rainsensor is not None
    assert (
        rainsensor.attributes.get("friendly_name") == "Rain Bird Controller Rainsensor"
    )

    entity_entry = entity_registry.async_get(
        "binary_sensor.rain_bird_controller_rainsensor"
    )
    assert not entity_entry
