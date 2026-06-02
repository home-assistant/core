"""Tests for the Duco sensor platform."""

import logging
from unittest.mock import AsyncMock

from duco_connectivity import (
    DucoConnectionError,
    DucoError,
    Node,
    NodeGeneralInfo,
    NodeSensorInfo,
    NodeType,
    NodeVentilationInfo,
    VentilationState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
) -> MockConfigEntry:
    """Set up only the sensor platform for testing."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    return await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])


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
        "sensor.bedroom_valve_humidity_air_quality_index",
        "sensor.hall_valve_co2_air_quality_index",
        "sensor.kitchen_rh_humidity_air_quality_index",
        "sensor.office_co2_co2_air_quality_index",
        "sensor.study_valve_co2_air_quality_index",
        "sensor.study_valve_humidity_air_quality_index",
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
    """Test sensor entities become unavailable when async_get_nodes raises DucoError."""
    mock_duco_client.async_get_nodes = AsyncMock(side_effect=DucoError("api error"))

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.office_co2_carbon_dioxide")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(DucoError("lan info error"), id="duco_error"),
        pytest.param(DucoConnectionError("lan info offline"), id="connection_error"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_lan_info_failures_keep_node_entities_available(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test node entities stay available when LAN info retrieval fails."""
    mock_duco_client.async_get_lan_info = AsyncMock(side_effect=exception)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.office_co2_carbon_dioxide")
    assert state is not None
    assert state.state == "405"

    state = hass.states.get("sensor.living_signal_strength")
    assert state is not None
    assert state.state == "-60"


@pytest.mark.parametrize(
    ("node_id", "expected_entity_id", "expected_state"),
    [
        (
            200,
            "sensor.new_rh_sensor_humidity",
            "55.0",
        ),
        (
            201,
            "sensor.new_valve_carbon_dioxide",
            "575",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_new_node_added_dynamically(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    dynamic_sensor_nodes: dict[int, Node],
    freezer: FrozenDateTimeFactory,
    node_id: int,
    expected_entity_id: str,
    expected_state: str,
) -> None:
    """Test a new node appearing in coordinator data creates entities automatically."""
    assert hass.states.get(expected_entity_id) is None

    new_node = dynamic_sensor_nodes[node_id]
    mock_duco_client.async_get_nodes.return_value = [*mock_sensor_nodes, new_node]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(expected_entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
async def test_deregistered_node_removes_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a node disappearing from the API removes its device from the registry."""
    device_registry = dr.async_get(hass)

    # Verify node 2 (UCCO2 RF sensor) device exists before deregistration.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_2")}
    )
    assert device is not None

    # Simulate the firmware removing the deregistered node from the API response.
    mock_duco_client.async_get_nodes.return_value = [
        node for node in mock_sensor_nodes if node.node_id != 2
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The device should be removed from the device registry.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_2")}
    )
    assert device is None


@pytest.mark.usefixtures("init_integration")
async def test_unknown_node_type_logs_warning_and_creates_no_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a node with an unknown type logs a warning and creates no entities."""
    unknown_node = Node(
        node_id=99,
        general=NodeGeneralInfo(
            node_type=NodeType.UNKNOWN,
            sub_type=0,
            network_type="RF",
            parent=1,
            asso=1,
            name="Unsupported device",
            identify=0,
        ),
        ventilation=None,
        sensor=None,
    )

    mock_duco_client.async_get_nodes.return_value = [*mock_sensor_nodes, unknown_node]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "99" in caplog.text
    assert "unsupported" in caplog.text.lower()
    assert hass.states.get("sensor.unsupported_device_humidity") is None

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_99")}
    )
    assert device is None


@pytest.mark.usefixtures("init_integration")
async def test_previously_unknown_node_gets_entities_after_type_becomes_known(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test UNKNOWN type node is retried and gets entities once the type resolves."""
    node_id = 99
    ventilation = NodeVentilationInfo(
        state="AUTO", time_state_remain=0, time_state_end=0, mode="-", flow_lvl_tgt=None
    )
    sensor = NodeSensorInfo(co2=None, iaq_co2=None, rh=62.0, iaq_rh=70, temp=21.0)

    def _make_node(node_type: NodeType | str) -> Node:
        """Create a Node with the given node type for use in tests."""
        return Node(
            node_id=node_id,
            general=NodeGeneralInfo(
                node_type=node_type,
                sub_type=0,
                network_type="RF",
                parent=1,
                asso=1,
                name="Future sensor",
                identify=0,
            ),
            ventilation=ventilation,
            sensor=sensor,
        )

    # First poll: UNKNOWN type — no entities created.
    mock_duco_client.async_get_nodes.return_value = [
        *mock_sensor_nodes,
        _make_node(NodeType.UNKNOWN),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.future_sensor_humidity") is None

    # Second poll: type now resolved — entities must be created.
    mock_duco_client.async_get_nodes.return_value = [
        *mock_sensor_nodes,
        _make_node("BSRH"),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.future_sensor_humidity")
    assert state is not None
    assert state.state == "62.0"


@pytest.mark.usefixtures("init_integration")
async def test_unknown_node_logged_at_debug(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that UNKNOWN nodes are logged at DEBUG level on every coordinator update."""
    unknown_node = Node(
        node_id=99,
        general=NodeGeneralInfo(
            node_type=NodeType.UNKNOWN,
            sub_type=0,
            network_type="RF",
            parent=1,
            asso=1,
            name="Future sensor",
            identify=0,
        ),
        ventilation=NodeVentilationInfo(
            state="AUTO",
            time_state_remain=0,
            time_state_end=0,
            mode="-",
            flow_lvl_tgt=None,
        ),
        sensor=NodeSensorInfo(co2=None, iaq_co2=None, rh=None, iaq_rh=None, temp=None),
    )
    mock_duco_client.async_get_nodes.return_value = [*mock_sensor_nodes, unknown_node]

    with caplog.at_level(logging.WARNING, logger="homeassistant.components.duco"):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "has an unsupported device type" not in caplog.text

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.duco"):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "has an unsupported device type" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_ventilation_state_unknown_returns_state_unknown(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that VentilationState.UNKNOWN makes the sensor report unknown."""
    box_node = next(n for n in mock_sensor_nodes if n.general.node_type == NodeType.BOX)
    updated_nodes = [
        Node(
            node_id=box_node.node_id,
            general=box_node.general,
            ventilation=NodeVentilationInfo(
                state=VentilationState.UNKNOWN,
                time_state_remain=0,
                time_state_end=0,
                mode="-",
                flow_lvl_tgt=None,
            ),
            sensor=box_node.sensor,
        )
        if n is box_node
        else n
        for n in mock_sensor_nodes
    ]
    mock_duco_client.async_get_nodes.return_value = updated_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.living_ventilation_state")
    assert state is not None
    assert state.state == STATE_UNKNOWN
