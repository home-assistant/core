"""Tests for the Duco sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError
from duco.models import Node, NodeVentilationInfo
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

_SENSOR_ENTITY = "sensor.living_ventilation_level"


@pytest.mark.usefixtures("init_sensor_integration")
async def test_sensor_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the sensor entity is created with the correct state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("ventilation_state", "expected_level"),
    [
        ("EMPT", "off"),
        ("AUTO", "auto"),
        ("AUT1", "auto"),
        ("AUT2", "auto"),
        ("AUT3", "auto"),
        ("CNT1", "1"),
        ("MAN1", "1"),
        ("CNT2", "2"),
        ("MAN2", "2"),
        ("CNT3", "3"),
        ("MAN3", "3"),
    ],
)
async def test_sensor_level_mapping(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    ventilation_state: str,
    expected_level: str,
) -> None:
    """Test that all ventilation states map to the correct sensor level."""
    mock_duco_client.async_get_nodes.return_value = [
        Node(
            node_id=mock_nodes[0].node_id,
            general=mock_nodes[0].general,
            ventilation=NodeVentilationInfo(
                state=ventilation_state,
                time_state_remain=0,
                time_state_end=0,
                mode=ventilation_state,
                flow_lvl_tgt=0,
            ),
        )
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_SENSOR_ENTITY)
    assert state is not None
    assert state.state == expected_level


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the sensor becomes unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_SENSOR_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
