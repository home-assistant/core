"""Test the Teslemetry select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from teslemetry_stream.const import Signal

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.teslemetry.select import LOW
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


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
    snapshot: SnapshotAssertion,
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

    # Assert the entities restored their values
    for entity_id in (
        "select.test_seat_heater_front_left",
        "select.test_seat_heater_front_right",
        "select.test_seat_heater_rear_left",
        "select.test_seat_heater_rear_center",
        "select.test_seat_heater_rear_right",
        "select.test_steering_wheel_heater",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=entity_id)
