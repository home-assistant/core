"""Tests for Bosch Alarm component."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from bosch_alarm_mode2.const import ALARM_MEMORY_PRIORITIES
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_observable, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.bosch_alarm.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor state."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_faulting_points(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that area faulting point count changes after arming the panel."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "sensor.area1_faulting_points"
    assert hass.states.get(entity_id).state == "0"

    area.faults = 1
    await call_observable(hass, area.ready_observer)
    assert hass.states.get(entity_id).state == "1"


async def test_alarm_faults(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that alarm state changes after arming the panel."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "sensor.area1_fire_alarm_issues"
    assert hass.states.get(entity_id).state == "no_issues"

    area.alarms_ids = [ALARM_MEMORY_PRIORITIES.FIRE_TROUBLE]
    await call_observable(hass, area.alarm_observer)

    assert hass.states.get(entity_id).state == "trouble"
