"""Test the Teslemetry select platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from teslemetry_stream.const import Signal

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.teslemetry.coordinator import ENERGY_INFO_INTERVAL
from homeassistant.components.teslemetry.select import LOW
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, SITE_INFO, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


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
        # Path 3: In VPP, Export enabled but state shows disabled (current_option is NEVER)
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
