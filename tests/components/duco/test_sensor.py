"""Tests for the Duco sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import Node, NodeGeneralInfo, NodeSensorInfo, NodeVentilationInfo
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the sensor platform for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_entities_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that sensor entities are created with the correct state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_iaq_sensor_entities_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that IAQ sensor entities are disabled by default."""
    for entity_id in (
        "sensor.bathroom_rh_humidity_air_quality_index",
        "sensor.office_co2_co2_air_quality_index",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_diagnostic_sensor_entities_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensor entities are disabled by default."""
    for entity_id in ("sensor.living_signal_strength",):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that sensor entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.office_co2_carbon_dioxide")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_duco_error_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that sensor entities become unavailable when async_get_nodes raises DucoError."""
    mock_duco_client.async_get_nodes = AsyncMock(side_effect=DucoError("api error"))

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.office_co2_carbon_dioxide")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_lan_info_duco_error_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when async_get_lan_info raises DucoError."""
    mock_duco_client.async_get_lan_info = AsyncMock(
        side_effect=DucoError("lan info error")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.living_signal_strength")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_new_node_added_dynamically(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a new node appearing in coordinator data creates entities automatically."""
    assert hass.states.get("sensor.new_rh_sensor_humidity") is None

    new_node = Node(
        node_id=200,
        general=NodeGeneralInfo(
            node_type="BSRH",
            sub_type=0,
            network_type="RF",
            parent=1,
            asso=1,
            name="New RH sensor",
            identify=0,
        ),
        ventilation=NodeVentilationInfo(
            state="AUTO",
            time_state_remain=0,
            time_state_end=0,
            mode="-",
            flow_lvl_tgt=None,
        ),
        sensor=NodeSensorInfo(
            co2=None,
            iaq_co2=None,
            rh=55.0,
            iaq_rh=70,
        ),
    )
    mock_duco_client.async_get_nodes.return_value = [*mock_nodes, new_node]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.new_rh_sensor_humidity")
    assert state is not None
    assert state.state == "55.0"


@pytest.mark.usefixtures("init_integration")
async def test_deregistered_node_removes_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a node disappearing from the API removes its device from the registry."""
    device_registry = dr.async_get(hass)

    # Verify node 2 (UCCO2 RF sensor) device exists before deregistration.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_2")}
    )
    assert device is not None

    # Simulate the firmware removing the deregistered node from the API response.
    mock_duco_client.async_get_nodes.return_value = [
        node for node in mock_nodes if node.node_id != 2
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The device should be removed from the device registry.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_2")}
    )
    assert device is None
