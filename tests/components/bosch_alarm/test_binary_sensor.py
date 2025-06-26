"""Tests for Bosch Alarm component."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from bosch_alarm_mode2.const import ALARM_PANEL_FAULTS
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_observable, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.bosch_alarm.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the binary sensor state."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("model", ["b5512"])
async def test_panel_faults(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that fault sensor state changes after inducing a fault."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.bosch_b5512_us1b_battery"
    assert hass.states.get(entity_id).state == STATE_OFF
    mock_panel.panel_faults_ids = [ALARM_PANEL_FAULTS.BATTERY_LOW]
    await call_observable(hass, mock_panel.faults_observer)
    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize("model", ["b5512"])
async def test_area_ready_to_arm(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that fault sensor state changes after inducing a fault."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.area1_area_ready_to_arm_away"
    entity_id_2 = "binary_sensor.area1_area_ready_to_arm_home"
    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id_2).state == STATE_ON
    area.all_ready = False
    await call_observable(hass, area.status_observer)
    assert hass.states.get(entity_id).state == STATE_OFF
    assert hass.states.get(entity_id_2).state == STATE_ON
    area.part_ready = False
    await call_observable(hass, area.status_observer)
    assert hass.states.get(entity_id).state == STATE_OFF
    assert hass.states.get(entity_id_2).state == STATE_OFF
