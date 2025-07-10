"""Test the Teslemetry number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the number entities are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_services(
    hass: HomeAssistant, mock_vehicle_data: AsyncMock
) -> None:
    """Tests that the number services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.NUMBER])

    entity_id = "number.test_charge_current"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_charging_amps",
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
        "tesla_fleet_api.teslemetry.Vehicle.set_charge_limit",
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
        "tesla_fleet_api.teslemetry.EnergySite.backup",
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
        "tesla_fleet_api.teslemetry.EnergySite.off_grid_vehicle_charging_reserve",
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


async def test_number_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the number entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.CHARGE_CURRENT_REQUEST: 24,
                Signal.CHARGE_CURRENT_REQUEST_MAX: 32,
                Signal.CHARGE_LIMIT_SOC: 99,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.NUMBER])

    # Assert the entities restored their values
    for entity_id in (
        "number.test_charge_current",
        "number.test_charge_limit",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-state")
