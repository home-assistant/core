"""Test the Teslemetry select platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.teslemetry.select import LOW
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the select entities are correct."""

    entry = await setup_platform(hass, [Platform.SELECT])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_select_offline(
    hass: HomeAssistant,
    mock_vehicle_data,
) -> None:
    """Tests that the select entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.SELECT])
    state = hass.states.get("select.test_seat_heater_front_left")
    assert state.state == STATE_UNKNOWN


async def test_select_services(hass: HomeAssistant, mock_vehicle_data) -> None:
    """Tests that the select services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.SELECT])

    entity_id = "select.test_seat_heater_front_left"
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.remote_seat_heater_request",
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
        "homeassistant.components.teslemetry.VehicleSpecific.remote_steering_wheel_heat_level_request",
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
        "homeassistant.components.teslemetry.EnergySpecific.operation",
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
        "homeassistant.components.teslemetry.EnergySpecific.grid_import_export",
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
