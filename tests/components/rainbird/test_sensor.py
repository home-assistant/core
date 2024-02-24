"""Tests for rainbird sensor platform."""

from http import HTTPStatus

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    RAIN_DELAY,
    RAIN_DELAY_OFF,
    mock_response_error,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    expected_state: str,
) -> None:
    """Test sensor platform."""

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Rain Bird Controller Raindelay",
        "icon": "mdi:water-off",
    }

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert entity_entry
    assert entity_entry.unique_id == "4c:a1:61:00:11:22-raindelay"


@pytest.mark.parametrize(
    ("config_entry_unique_id", "config_entry_data", "setup_config_entry"),
    [
        # Config entry setup without a unique id since it had no serial number
        (
            None,
            {
                **CONFIG_ENTRY_DATA_OLD_FORMAT,
                "serial_number": 0,
            },
            None,
        ),
    ],
)
async def test_sensor_no_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    responses: list[AiohttpClientMockResponse],
    config_entry_unique_id: str | None,
    config_entry: MockConfigEntry,
) -> None:
    """Test sensor platform with no unique id."""

    # Failure to migrate config entry to a unique id
    responses.insert(0, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.LOADED

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.attributes.get("friendly_name") == "Rain Bird Controller Raindelay"

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert (entity_entry is None) == (config_entry_unique_id is None)
