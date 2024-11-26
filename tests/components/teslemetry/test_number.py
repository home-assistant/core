"""Test the Teslemetry number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the number entities are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_number_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the number entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.NUMBER])
    state = hass.states.get("number.test_charge_current")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_services(
    hass: HomeAssistant, mock_vehicle_data: AsyncMock
) -> None:
    """Tests that the number services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.NUMBER])

    entity_id = "number.test_charge_current"
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.set_charging_amps",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 16},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "16"
        call.assert_called_once()

    entity_id = "number.test_charge_limit"
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.set_charge_limit",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 60},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "60"
        call.assert_called_once()

    entity_id = "number.energy_site_backup_reserve"
    with patch(
        "homeassistant.components.teslemetry.EnergySpecific.backup",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 80,
            },
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "80"
        call.assert_called_once()

    entity_id = "number.energy_site_off_grid_reserve"
    with patch(
        "homeassistant.components.teslemetry.EnergySpecific.off_grid_vehicle_charging_reserve",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 88},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "88"
        call.assert_called_once()
