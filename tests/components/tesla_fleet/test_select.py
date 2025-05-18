"""Test the Tesla Fleet select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tesla_fleet.select import LOW
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the select entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.SELECT])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_select_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the select entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, normal_config_entry, [Platform.SELECT])
    state = hass.states.get("select.test_seat_heater_front_left")
    assert state.state == STATE_UNKNOWN


async def test_select_services(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the select services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, normal_config_entry, [Platform.SELECT])

    entity_id = "select.test_seat_heater_front_left"
    with (
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.remote_seat_heater_request",
            return_value=COMMAND_OK,
        ) as remote_seat_heater_request,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.auto_conditioning_start",
            return_value=COMMAND_OK,
        ) as auto_conditioning_start,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LOW},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LOW
        auto_conditioning_start.assert_called_once()
        remote_seat_heater_request.assert_called_once()

    entity_id = "select.test_steering_wheel_heater"
    with (
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.remote_steering_wheel_heat_level_request",
            return_value=COMMAND_OK,
        ) as remote_steering_wheel_heat_level_request,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.auto_conditioning_start",
            return_value=COMMAND_OK,
        ) as auto_conditioning_start,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LOW},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LOW
        auto_conditioning_start.assert_called_once()
        remote_steering_wheel_heat_level_request.assert_called_once()

    entity_id = "select.energy_site_operation_mode"
    with patch(
        "tesla_fleet_api.tesla.EnergySite.operation",
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
        "tesla_fleet_api.tesla.EnergySite.grid_import_export",
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
