"""Test the Teslemetry switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


async def test_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the switch entities are correct."""

    entry = await setup_platform(hass, [Platform.SWITCH])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_switch_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the switch entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.SWITCH])
    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


async def test_switch_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the switch entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.SWITCH])
    state = hass.states.get("switch.test_auto_seat_climate_left")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("name", "on", "off"),
    [
        ("test_charge", "VehicleSpecific.charge_start", "VehicleSpecific.charge_stop"),
        (
            "test_auto_seat_climate_left",
            "VehicleSpecific.remote_auto_seat_climate_request",
            "VehicleSpecific.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_seat_climate_right",
            "VehicleSpecific.remote_auto_seat_climate_request",
            "VehicleSpecific.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_steering_wheel_heater",
            "VehicleSpecific.remote_auto_steering_wheel_heat_climate_request",
            "VehicleSpecific.remote_auto_steering_wheel_heat_climate_request",
        ),
        (
            "test_defrost",
            "VehicleSpecific.set_preconditioning_max",
            "VehicleSpecific.set_preconditioning_max",
        ),
        (
            "energy_site_storm_watch",
            "EnergySpecific.storm_mode",
            "EnergySpecific.storm_mode",
        ),
        (
            "energy_site_allow_charging_from_grid",
            "EnergySpecific.grid_import_export",
            "EnergySpecific.grid_import_export",
        ),
        (
            "test_sentry_mode",
            "VehicleSpecific.set_sentry_mode",
            "VehicleSpecific.set_sentry_mode",
        ),
    ],
)
async def test_switch_services(
    hass: HomeAssistant, name: str, on: str, off: str
) -> None:
    """Tests that the switch service calls work."""

    await setup_platform(hass, [Platform.SWITCH])

    entity_id = f"switch.{name}"
    with patch(
        f"homeassistant.components.teslemetry.{on}",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        call.assert_called_once()

    with patch(
        f"homeassistant.components.teslemetry.{off}",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF
        call.assert_called_once()
