"""Test the Teslemetry select platform."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from tesla_fleet_api.exceptions import InvalidCommand
from teslemetry_stream.const import Signal

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.teslemetry.coordinator import (
    ENERGY_INFO_INTERVAL,
    VEHICLE_INTERVAL,
)
from homeassistant.components.teslemetry.select import HIGH, LEVEL, LOW, MEDIUM, OFF
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import (
    COMMAND_ERRORS,
    COMMAND_OK,
    METADATA,
    METADATA_LEGACY,
    SITE_INFO,
    VEHICLE_DATA_ALT,
)

from tests.common import async_fire_time_changed

# Entity description keys for the rear seat-heater entities gated by config.
REAR_LEFT = "climate_state_seat_heater_rear_left"
REAR_CENTER = "climate_state_seat_heater_rear_center"
REAR_RIGHT = "climate_state_seat_heater_rear_right"
THIRD_LEFT = "climate_state_seat_heater_third_row_left"
THIRD_RIGHT = "climate_state_seat_heater_third_row_right"
ALL_REAR_KEYS = {REAR_LEFT, REAR_CENTER, REAR_RIGHT, THIRD_LEFT, THIRD_RIGHT}

VEHICLE_VIN = "LRW3F7EK4NC700000"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the select entities are correct."""

    entry = await setup_platform(hass, [Platform.SELECT])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param({}, set(), id="no_config"),
        pytest.param(
            {"rear_seat_heaters": 0, "third_row_seats": "None"},
            set(),
            id="0_no_rear_heaters",
        ),
        pytest.param(
            {"rear_seat_heaters": 1, "third_row_seats": "None"},
            {REAR_LEFT, REAR_CENTER, REAR_RIGHT},
            id="1_heated_rear_bench",
        ),
        pytest.param(
            {"rear_seat_heaters": 2, "third_row_seats": "None"},
            {REAR_LEFT, REAR_RIGHT},
            id="2_legacy_model_s_outboard_only",
        ),
        pytest.param(
            {"rear_seat_heaters": 3, "third_row_seats": "FoldFlatPowerStrutSeats"},
            {REAR_LEFT, REAR_CENTER, REAR_RIGHT, THIRD_LEFT, THIRD_RIGHT},
            id="3_model_x_with_third_row",
        ),
        pytest.param(
            {"rear_seat_heaters": 3, "third_row_seats": "None"},
            {REAR_LEFT, REAR_CENTER, REAR_RIGHT},
            id="3_model_x_five_seat_no_third_row",
        ),
    ],
)
async def test_rear_seat_heater_configurations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
    config: dict[str, int | str],
    expected: set[str],
) -> None:
    """Verify which rear seat-heater entities exist per rear_seat_heaters config.

    rear_seat_heaters is an undocumented Tesla enum. Behaviour inferred from
    vehicle models/years/config observed across the fleet:
      0 - no heated rear seats
      1 - heated rear bench: left, center, right (Model 3/Y, modern S/X, ...)
      2 - outboard rear only: left, right, no center (classic Model S)
      3 - heated rear bench plus third row (Model X)
    Third-row heaters additionally require an actual third row, since some
    5-seat Model X report 3 without having a third row. third_row_seats is a
    string ("None" when absent), not a bool.
    """
    metadata = deepcopy(METADATA)
    metadata["vehicles"][VEHICLE_VIN]["config"] = config
    mock_metadata.return_value = metadata

    entry = await setup_platform(hass, [Platform.SELECT])

    created = {
        entity.unique_id.removeprefix(f"{VEHICLE_VIN}-")
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert (created & ALL_REAR_KEYS) == expected


async def test_select_services(hass: HomeAssistant, mock_vehicle_data) -> None:
    """Tests that the select services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.SELECT])

    entity_id = "select.test_seat_heater_front_left"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.remote_seat_heater_request",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LOW},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LOW
        call.assert_called_once()

    entity_id = "select.test_steering_wheel_heater"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.remote_steering_wheel_heat_level_request",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LOW},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LOW
        call.assert_called_once()

    entity_id = "select.energy_site_operation_mode"
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.operation",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: EnergyOperationMode.AUTONOMOUS.value,
            },
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == EnergyOperationMode.AUTONOMOUS.value
        call.assert_called_once()

    entity_id = "select.energy_site_allow_export"
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.grid_import_export",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: EnergyExportMode.BATTERY_OK.value},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == EnergyExportMode.BATTERY_OK.value
        call.assert_called_once()


@pytest.mark.parametrize(
    ("entity_id", "seat_position"),
    [
        ("select.test_seat_cooler_front_left", 1),
        ("select.test_seat_cooler_front_right", 2),
    ],
)
async def test_seat_cooler_services(
    hass: HomeAssistant,
    mock_metadata: AsyncMock,
    mock_vehicle_data: AsyncMock,
    entity_id: str,
    seat_position: int,
) -> None:
    """Test the seat cooler entities send the 1-indexed seat position.

    remote_seat_cooler_request is 1-indexed (front-left=1, front-right=2),
    unlike the 0-indexed Seat enum used for the seat heaters.
    """
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    metadata = deepcopy(METADATA)
    metadata["vehicles"][VEHICLE_VIN]["config"] = {"has_seat_cooling": True}
    mock_metadata.return_value = metadata

    await setup_platform(hass, [Platform.SELECT])

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.remote_seat_cooler_request",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LOW},
            blocking=True,
        )
        assert hass.states.get(entity_id).state == LOW
        call.assert_called_once_with(seat_position, LEVEL[LOW])


async def test_seat_cooler_polling(
    hass: HomeAssistant,
    mock_metadata: AsyncMock,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test the seat cooler entities read polled state from seat_fan_front_*."""
    metadata = deepcopy(METADATA)
    metadata["vehicles"][VEHICLE_VIN]["polling"] = True
    metadata["vehicles"][VEHICLE_VIN]["config"] = {"has_seat_cooling": True}
    mock_metadata.return_value = metadata

    data = deepcopy(VEHICLE_DATA_ALT)
    data["response"]["climate_state"]["seat_fan_front_left"] = 2
    data["response"]["climate_state"]["seat_fan_front_right"] = 0
    mock_vehicle_data.return_value = data

    await setup_platform(hass, [Platform.SELECT])

    assert hass.states.get("select.test_seat_cooler_front_left").state == MEDIUM
    assert hass.states.get("select.test_seat_cooler_front_right").state == OFF


@pytest.mark.parametrize("response", COMMAND_ERRORS)
async def test_select_command_errors(
    hass: HomeAssistant, mock_vehicle_data: AsyncMock, response: dict
) -> None:
    """Tests that vehicle command failures raise HomeAssistantError."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.SELECT])

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.remote_seat_heater_request",
            return_value=response,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.test_seat_heater_front_left", ATTR_OPTION: LOW},
            blocking=True,
        )


async def test_select_command_exception(hass: HomeAssistant) -> None:
    """Tests that an energy command SDK exception raises HomeAssistantError."""
    await setup_platform(hass, [Platform.SELECT])

    with (
        patch(
            "tesla_fleet_api.teslemetry.EnergySite.operation",
            side_effect=InvalidCommand,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.energy_site_operation_mode",
                ATTR_OPTION: EnergyOperationMode.AUTONOMOUS.value,
            },
            blocking=True,
        )


async def test_select_invalid_data(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the select entities handle invalid data."""

    broken_data = VEHICLE_DATA_ALT.copy()
    broken_data["response"]["climate_state"]["seat_heater_left"] = "green"
    broken_data["response"]["climate_state"]["steering_wheel_heat_level"] = "yellow"

    mock_vehicle_data.return_value = broken_data
    await setup_platform(hass, [Platform.SELECT])
    state = hass.states.get("select.test_seat_heater_front_left")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("select.test_steering_wheel_heater")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_streaming(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the select entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.SELECT])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SEAT_HEATER_LEFT: 0,
                Signal.SEAT_HEATER_RIGHT: 1,
                Signal.SEAT_HEATER_REAR_LEFT: 2,
                Signal.SEAT_HEATER_REAR_RIGHT: 3,
                Signal.HVAC_STEERING_WHEEL_HEAT_LEVEL: 0,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.SELECT])

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("select.test_seat_heater_front_left").state == "off"
    assert hass.states.get("select.test_seat_heater_front_right").state == "low"
    assert hass.states.get("select.test_seat_heater_rear_left").state == "medium"
    assert hass.states.get("select.test_seat_heater_rear_center").state == STATE_UNKNOWN
    assert hass.states.get("select.test_seat_heater_rear_right").state == "high"
    assert hass.states.get("select.test_steering_wheel_heater").state == "off"


async def _drive_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    value: int,
) -> None:
    """Push a steering wheel level through the polling path."""
    data = deepcopy(VEHICLE_DATA_ALT)
    data["response"]["climate_state"]["steering_wheel_heat_level"] = value
    mock_vehicle_data.return_value = data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)


async def _drive_streaming(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    value: int,
) -> None:
    """Push a steering wheel level through the streaming path."""
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {Signal.HVAC_STEERING_WHEEL_HEAT_LEVEL: value},
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )


@pytest.mark.parametrize(
    ("metadata", "driver"),
    [
        pytest.param(METADATA_LEGACY, _drive_polling, id="polling"),
        pytest.param(METADATA, _drive_streaming, id="streaming"),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(3, HIGH, id="level_3_high"),
        pytest.param(4, HIGH, id="out_of_range_clamped"),
    ],
)
async def test_steering_wheel_heat_levels(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_metadata: AsyncMock,
    mock_add_listener: AsyncMock,
    metadata: dict,
    driver: Callable[
        [HomeAssistant, FrozenDateTimeFactory, AsyncMock, AsyncMock, int],
        Awaitable[None],
    ],
    value: int,
    expected: str,
) -> None:
    """Level 3 resolves to high and a value beyond the range clamps to high."""
    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_metadata.return_value = metadata

    await setup_platform(hass, [Platform.SELECT])

    await driver(hass, freezer, mock_vehicle_data, mock_add_listener, value)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_steering_wheel_heater")
    assert state.state == expected


async def test_export_rule_restore(
    hass: HomeAssistant,
    mock_site_info: AsyncMock,
) -> None:
    """Test export rule entity when value is missing due to VPP enrollment."""
    # Mock energy site with missing export rule (VPP scenario)
    vpp_site_info = deepcopy(SITE_INFO)
    # Remove the customer_preferred_export_rule to simulate VPP enrollment
    del vpp_site_info["response"]["components"]["customer_preferred_export_rule"]
    mock_site_info.side_effect = lambda: vpp_site_info

    # Set up platform
    entry = await setup_platform(hass, [Platform.SELECT])

    # Entity should exist but have no current option initially
    entity_id = "select.energy_site_allow_export"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Test service call works even when value is missing (VPP enrolled)
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.grid_import_export",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: EnergyExportMode.BATTERY_OK.value,
            },
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == EnergyExportMode.BATTERY_OK.value
        call.assert_called_once()

    # Reload the platform to test state restoration
    await reload_platform(hass, entry, [Platform.SELECT])

    # The entity should restore the previous state since API value is still missing
    state = hass.states.get(entity_id)
    assert state.state == EnergyExportMode.BATTERY_OK.value


@pytest.mark.parametrize(
    ("previous_data", "new_data", "expected_state"),
    [
        # Path 1: Customer selected export option (has value)
        (
            {
                "customer_preferred_export_rule": "battery_ok",
                "non_export_configured": None,
            },
            {
                "customer_preferred_export_rule": "pv_only",
                "non_export_configured": None,
            },
            EnergyExportMode.PV_ONLY.value,
        ),
        # Path 2: In VPP, Export is disabled (non_export_configured is True)
        (
            {
                "customer_preferred_export_rule": "battery_ok",
                "non_export_configured": None,
            },
            {
                "customer_preferred_export_rule": None,
                "non_export_configured": True,
            },
            EnergyExportMode.NEVER.value,
        ),
        # Path 3: In VPP, Export enabled but state shows disabled
        # (current_option is NEVER)
        (
            {
                "customer_preferred_export_rule": "never",
                "non_export_configured": None,
            },
            {
                "customer_preferred_export_rule": None,
                "non_export_configured": None,
            },
            STATE_UNKNOWN,
        ),
        # Path 4: In VPP Mode, Export isn't disabled, use last known state
        (
            {
                "customer_preferred_export_rule": "battery_ok",
                "non_export_configured": None,
            },
            {
                "customer_preferred_export_rule": None,
                "non_export_configured": None,
            },
            EnergyExportMode.BATTERY_OK.value,
        ),
    ],
)
async def test_export_rule_update_attrs_logic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_site_info: AsyncMock,
    previous_data: dict,
    new_data: str | None,
    expected_state: str,
) -> None:
    """Test all logic paths in TeslemetryExportRuleSelectEntity._async_update_attrs."""
    # Create site info with the test data
    test_site_info = deepcopy(SITE_INFO)
    test_site_info["response"]["components"].update(previous_data)
    mock_site_info.side_effect = lambda: test_site_info

    # Set up platform
    await setup_platform(hass, [Platform.SELECT])

    # Change the state
    test_site_info = deepcopy(SITE_INFO)
    test_site_info["response"]["components"].update(new_data)
    mock_site_info.side_effect = lambda: test_site_info

    # Coordinator refresh
    freezer.tick(ENERGY_INFO_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check the final state matches expected
    state = hass.states.get("select.energy_site_allow_export")
    assert state
    assert state.state == expected_state
