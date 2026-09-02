"""Tests for the Duco binary sensor platform."""

from unittest.mock import AsyncMock

from duco_connectivity import (
    DiagComponent,
    DiagInfo,
    DucoConnectionError,
    DucoError,
    Node,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.duco.const import BOX_NODE_ID, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed

VENTILATION_PROBLEM_ENTITY_ID = "binary_sensor.living_ventilation"


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
) -> MockConfigEntry:
    """Set up only the binary sensor platform for testing."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    return await setup_platform_integration(
        hass, mock_config_entry, [Platform.BINARY_SENSOR]
    )


async def test_diagnostic_binary_sensor_entity_registry_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the diagnostic binary sensor entity registry defaults."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status="Ok"),
            DiagComponent(component="Filter", status="Ok"),
            DiagComponent(component="VentCool", status="Ok"),
            DiagComponent(component="SunCtrl", status="Ok"),
            DiagComponent(component="Future Mode", status="Ok"),
        )
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    for entity_id in (
        "binary_sensor.living_future_mode",
        "binary_sensor.living_sun_control",
        "binary_sensor.living_ventilation_cooling",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        assert entry.original_device_class is BinarySensorDeviceClass.PROBLEM

    for entity_id in (
        "binary_sensor.living_filter",
        VENTILATION_PROBLEM_ENTITY_ID,
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is None
        assert entry.original_device_class is BinarySensorDeviceClass.PROBLEM


@pytest.mark.parametrize(
    ("raw_status", "expected_state"),
    [
        pytest.param("Ok", STATE_OFF, id="ok"),
        pytest.param("Error", STATE_ON, id="error"),
        pytest.param("Disable", STATE_ON, id="disabled"),
        pytest.param("FutureState", STATE_UNKNOWN, id="unknown"),
    ],
)
async def test_diagnostic_binary_sensor_problem_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    raw_status: str,
    expected_state: str,
) -> None:
    """Test diagnostic statuses map to the expected problem state."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status=raw_status),
        )
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_diagnostic_binary_sensors_added_after_initial_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostic binary sensors can be added after an empty response."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo()

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(VENTILATION_PROBLEM_ENTITY_ID) is None

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(DiagComponent(component="Ventilation", status="Error"),)
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status="Error"),
            DiagComponent(component="Filter", status="Ok"),
        )
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.living_filter")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_diagnostic_binary_sensors_wait_for_box_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostic binary sensors are added when the box reappears."""
    mock_duco_client.async_get_nodes.return_value = [
        node for node in mock_sensor_nodes if node.node_id != BOX_NODE_ID
    ]

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(VENTILATION_PROBLEM_ENTITY_ID) is None

    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "diagnostic_subsystems",
    [
        pytest.param((), id="missing"),
        pytest.param(
            (DiagComponent(component="Ventilation", status="Unexpected"),),
            id="unknown_status",
        ),
    ],
)
async def test_diagnostic_binary_sensor_becomes_unknown_without_known_status(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    diagnostic_subsystems: tuple[DiagComponent, ...],
) -> None:
    """Test diagnostic binary sensors report unknown without a known status."""
    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=diagnostic_subsystems
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(DucoConnectionError("offline"), id="connection_error"),
        pytest.param(DucoError("api error"), id="duco_error"),
    ],
)
async def test_diagnostic_binary_sensor_becomes_unavailable_on_refresh_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: DucoError,
) -> None:
    """Test diagnostic binary sensors become unavailable on refresh errors."""
    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    mock_duco_client.async_get_diagnostics_info.side_effect = exception

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
