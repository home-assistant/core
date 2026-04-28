"""Tests for the Nobø Ecohub sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_hub_update

from tests.common import MockConfigEntry, snapshot_platform

TEMPERATURE_ENTITY = "sensor.floor_sensor_temperature"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform for these tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """All sensor entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_temperature_unknown_when_missing(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Missing temperature values surface as unknown state."""
    mock_nobo_hub.get_current_component_temperature.return_value = None
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY).state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_temperature_push_update(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Pushed hub updates refresh the temperature state."""
    assert hass.states.get(TEMPERATURE_ENTITY).state == "21.5"

    mock_nobo_hub.get_current_component_temperature.return_value = "19.3"
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY).state == "19.3"


@pytest.mark.usefixtures("init_integration")
async def test_component_removed_marks_unavailable(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A component removed via the Nobø app must not crash and goes unavailable."""
    mock_nobo_hub.components.pop("200000059091")
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE
