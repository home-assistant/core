"""Tests for the Duco sensor platform."""

from dataclasses import replace
import logging
from unittest.mock import AsyncMock

from duco_connectivity import (
    DucoConnectionError,
    DucoError,
    DucoUnsupportedCapabilityError,
    Node,
    NodeGeneralInfo,
    NodeSensorInfo,
    NodeType,
    NodeVentilationInfo,
    VentilationState,
    VentilationTemperatureInfo,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import BOX_NODE_ID, DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

FILTER_REMAINING_ENTITY_ID = "sensor.living_filter_remaining"
VENTILATION_TEMPERATURE_ENTITY_IDS = (
    "sensor.living_outdoor_air_temperature",
    "sensor.living_supply_air_temperature",
    "sensor.living_extract_air_temperature",
    "sensor.living_exhaust_air_temperature",
)


@pytest.mark.parametrize(
    "ventilation_node_type",
    [
        pytest.param(NodeType.BOX, id="box"),
        pytest.param(NodeType.VLV, id="vlv"),
        pytest.param(NodeType.VLVRH, id="vlvrh"),
        pytest.param(NodeType.VLVVOC, id="vlvvoc"),
        pytest.param(NodeType.VLVCO2, id="vlvco2"),
        pytest.param(NodeType.VLVCO2RH, id="vlvco2rh"),
        pytest.param(NodeType.EAV, id="eav"),
        pytest.param(NodeType.EAVRH, id="eavrh"),
        pytest.param(NodeType.EAVVOC, id="eavvoc"),
        pytest.param(NodeType.EAVCO2, id="eavco2"),
    ],
)
async def test_ventilation_related_sensors_created_for_supported_node_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    ventilation_node_type: NodeType,
) -> None:
    """Test ventilation-related sensors are created for supported node families."""
    supported_node = replace(
        mock_sensor_nodes[0],
        general=replace(mock_sensor_nodes[0].general, node_type=ventilation_node_type),
        ventilation=replace(
            mock_sensor_nodes[0].ventilation,
            flow_lvl_tgt=42,
            time_state_end=1700000459,
        ),
    )
    mock_duco_client.async_get_nodes.return_value = [
        supported_node,
        *mock_sensor_nodes[1:],
    ]

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get("sensor.living_ventilation_state")
    assert state is not None
    assert state.state == "auto"

    state = hass.states.get("sensor.living_target_flow_level")
    assert state is not None
    assert state.state == "42"

    state = hass.states.get("sensor.living_state_end_time")
    assert state is not None
    assert state.state == "2023-11-14T22:20:59+00:00"

    assert hass.states.get("sensor.office_co2_ventilation_state") is None
    assert hass.states.get("sensor.office_co2_target_flow_level") is None
    assert hass.states.get("sensor.office_co2_state_end_time") is None


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
@pytest.mark.parametrize(
    ("exception_type", "exception_message"),
    [
        pytest.param(DucoConnectionError, "offline", id="connection_error"),
        pytest.param(DucoError, "api error", id="duco_error"),
    ],
)
async def test_coordinator_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception_type: type[DucoError],
    exception_message: str,
) -> None:
    """Test sensor entities become unavailable when the coordinator update fails."""
    mock_duco_client.async_get_nodes.side_effect = exception_type(exception_message)

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


async def test_time_filter_remaining_missing_skips_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the filter timer sensor is not created when unsupported."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes

    mock_duco_client.async_get_time_filter_remaining = AsyncMock(
        side_effect=[None, 180]
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get(FILTER_REMAINING_ENTITY_ID) is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(FILTER_REMAINING_ENTITY_ID) is None


async def test_ventilation_temperatures_missing_skip_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unsupported ventilation temperatures never expose temperature states."""
    mock_duco_client.async_get_ventilation_temperature_info.side_effect = [
        DucoUnsupportedCapabilityError(400, "/info", '{"Code":3,"Result":"FAILED"}'),
        VentilationTemperatureInfo(temp_oda=5.5),
    ]

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in VENTILATION_TEMPERATURE_ENTITY_IDS:
        assert hass.states.get(entity_id) is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in VENTILATION_TEMPERATURE_ENTITY_IDS:
        assert hass.states.get(entity_id) is None


async def test_partial_ventilation_temperatures_only_expose_available_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test only populated ventilation temperature fields are exposed as states."""
    mock_duco_client.async_get_ventilation_temperature_info.return_value = (
        VentilationTemperatureInfo(temp_oda=5.5, temp_eta=21.4)
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get("sensor.living_outdoor_air_temperature")
    assert state is not None
    assert state.state == "5.5"

    state = hass.states.get("sensor.living_extract_air_temperature")
    assert state is not None
    assert state.state == "21.4"

    assert hass.states.get("sensor.living_supply_air_temperature") is None
    assert hass.states.get("sensor.living_exhaust_air_temperature") is None


async def test_time_filter_remaining_transient_failure_recovers_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the filter timer sensor is added once a transient startup failure recovers."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_time_filter_remaining = AsyncMock(
        side_effect=[DucoError("heat recovery info error"), 180]
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get(FILTER_REMAINING_ENTITY_ID) is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(FILTER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == "180"


@pytest.mark.parametrize(
    (
        "node_id",
        "expected_entity_id",
        "expected_state",
        "expected_disabled_entity_id",
    ),
    [
        (
            200,
            "sensor.new_rh_sensor_humidity",
            "55.0",
            "sensor.new_rh_sensor_humidity_air_quality_index",
        ),
        (
            201,
            "sensor.new_valve_carbon_dioxide",
            "575",
            "sensor.new_valve_co2_air_quality_index",
        ),
        (
            202,
            "sensor.new_box_co2_sensor_carbon_dioxide",
            "421",
            "sensor.new_box_co2_sensor_co2_air_quality_index",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_new_node_added_dynamically(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    dynamic_sensor_nodes: dict[int, Node],
    freezer: FrozenDateTimeFactory,
    node_id: int,
    expected_entity_id: str,
    expected_state: str,
    expected_disabled_entity_id: str,
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

    entry = entity_registry.async_get(expected_disabled_entity_id)
    assert entry is not None
    assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_deregistered_node_removes_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a node disappearing from the API removes its device from the registry."""
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_box_node_not_removed_on_transient_incomplete_node_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test BOX-linked entities survive a transient node list without node 1."""
    await setup_platform_integration(
        hass, mock_config_entry, [Platform.FAN, Platform.SENSOR]
    )

    box_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_{BOX_NODE_ID}")}
    )
    assert box_device is not None
    assert hass.states.get("fan.living") is not None

    mock_duco_client.async_get_nodes.return_value = [
        node for node in mock_sensor_nodes if node.node_id != BOX_NODE_ID
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{mock_config_entry.unique_id}_{BOX_NODE_ID}")}
        )
        is not None
    )
    state = hass.states.get("fan.living")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("fan.living")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


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
