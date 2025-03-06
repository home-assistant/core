"""Test Homee alarm control panels."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("service", "state"),
    [
        (SERVICE_ALARM_ARM_HOME, 0),
        (SERVICE_ALARM_ARM_NIGHT, 1),
        (SERVICE_ALARM_ARM_AWAY, 2),
        (SERVICE_ALARM_ARM_VACATION, 3),
    ],
)
async def test_alarm_control_panel_services(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    state: int,
) -> None:
    """Test alarm control panel services."""
    mock_homee.nodes = [build_mock_node("homee.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "alarm_control_panel.testhomee_status"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(-1, 1, state)


async def test_valve_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the valve snapshots."""
    mock_homee.nodes = [build_mock_node("homee.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    with patch(
        "homeassistant.components.homee.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
