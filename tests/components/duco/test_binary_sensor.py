"""Tests for the Duco binary sensor platform."""

import logging
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

DIAGNOSTIC_ERROR_TYPES = [
    pytest.param(DucoConnectionError, id="connection_error"),
    pytest.param(DucoError, id="duco_error"),
]


async def _async_refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger a coordinator refresh."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_diagnostic_binary_sensor_entity_registry_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the diagnostic binary sensor entity registry defaults."""
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status="Ok"),
            DiagComponent(component="Filter", status="Ok"),
            DiagComponent(component="VentCool", status="Ok"),
            DiagComponent(component="SunCtrl", status="Ok"),
        )
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    for entity_id, disabled_by in (
        (
            "binary_sensor.living_sun_control",
            er.RegistryEntryDisabler.INTEGRATION,
        ),
        (
            "binary_sensor.living_ventilation_cooling",
            er.RegistryEntryDisabler.INTEGRATION,
        ),
        ("binary_sensor.living_filter", None),
        (VENTILATION_PROBLEM_ENTITY_ID, None),
    ):
        assert (entry := entity_registry.async_get(entity_id)) is not None
        assert entry.disabled_by is disabled_by
        assert entry.original_device_class is BinarySensorDeviceClass.PROBLEM


async def test_unknown_diagnostic_subsystem_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unknown diagnostic subsystem is not exposed."""
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(DiagComponent(component="Future Mode", status="Error"),)
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert entity_registry.async_get("binary_sensor.living_future_mode") is None


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
    raw_status: str,
    expected_state: str,
) -> None:
    """Test diagnostic statuses map to the expected problem state."""
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status=raw_status),
        )
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert (state := hass.states.get(VENTILATION_PROBLEM_ENTITY_ID)) is not None
    assert state.state == expected_state
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM


async def test_diagnostic_binary_sensors_added_after_initial_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostic binary sensors can be added after an empty response."""
    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo()

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(VENTILATION_PROBLEM_ENTITY_ID) is None

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(DiagComponent(component="Ventilation", status="Error"),)
    )

    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_ON)

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=(
            DiagComponent(component="Ventilation", status="Error"),
            DiagComponent(component="Filter", status="Ok"),
        )
    )

    await _async_refresh(hass, freezer)

    assert hass.states.is_state("binary_sensor.living_filter", STATE_OFF)


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
    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_OFF)


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
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    diagnostic_subsystems: tuple[DiagComponent, ...],
) -> None:
    """Test diagnostic binary sensors report unknown without a known status."""
    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_OFF)

    mock_duco_client.async_get_diagnostics_info.return_value = DiagInfo(
        diagnostic_subsystems=diagnostic_subsystems
    )

    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_UNKNOWN)


@pytest.mark.parametrize("exception_type", DIAGNOSTIC_ERROR_TYPES)
async def test_diagnostics_refresh_failure_is_isolated_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    exception_type: type[DucoError],
) -> None:
    """Test a diagnostics refresh failure is isolated and recovers."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    await setup_platform_integration(
        hass, mock_config_entry, [Platform.BINARY_SENSOR, Platform.SENSOR]
    )

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_OFF)

    mock_duco_client.async_get_diagnostics_info.side_effect = exception_type("error")

    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_UNAVAILABLE)
    assert hass.states.is_state("sensor.office_co2_carbon_dioxide", "405")

    mock_duco_client.async_get_diagnostics_info.side_effect = None
    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_OFF)


@pytest.mark.parametrize("exception_type", DIAGNOSTIC_ERROR_TYPES)
async def test_initial_diagnostics_failure_is_isolated_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    exception_type: type[DucoError],
) -> None:
    """Test an initial diagnostics failure is isolated and recovers."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_diagnostics_info.side_effect = exception_type("error")

    await setup_platform_integration(
        hass, mock_config_entry, [Platform.BINARY_SENSOR, Platform.SENSOR]
    )

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(VENTILATION_PROBLEM_ENTITY_ID) is None
    assert hass.states.is_state("sensor.office_co2_carbon_dioxide", "405")

    mock_duco_client.async_get_diagnostics_info.side_effect = None
    await _async_refresh(hass, freezer)

    assert hass.states.is_state(VENTILATION_PROBLEM_ENTITY_ID, STATE_OFF)


async def test_diagnostics_availability_transitions_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test diagnostics availability transitions are logged once."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.duco.coordinator")
    mock_duco_client.async_get_diagnostics_info.side_effect = DucoError("error")

    await setup_platform_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])
    await _async_refresh(hass, freezer)

    mock_duco_client.async_get_diagnostics_info.side_effect = None
    await _async_refresh(hass, freezer)
    await _async_refresh(hass, freezer)

    assert [
        record.message
        for record in caplog.records
        if record.name == "homeassistant.components.duco.coordinator"
    ] == [
        "Duco diagnostics are unavailable: error",
        "Duco diagnostics are available again",
    ]
