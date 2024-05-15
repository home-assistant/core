"""Test the Teslemetry switch platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion
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

from . import assert_entities, setup_platform
from .const import COMMAND_OK


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the switch entities are correct."""

    entry = await setup_platform(hass, [Platform.SWITCH])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_switch_offline(
    hass: HomeAssistant,
    mock_vehicle_data,
) -> None:
    """Tests that the switch entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.SWITCH])
    state = hass.states.get("switch.test_defrost")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("name", "on", "off"),
    [
        ("charge", "VehicleSpecific.charge_start", "VehicleSpecific.charge_stop"),
        (
            "auto_seat_climate_left",
            "VehicleSpecific.remote_auto_seat_climate_request",
            "VehicleSpecific.remote_auto_seat_climate_request",
        ),
        (
            "auto_seat_climate_right",
            "VehicleSpecific.remote_auto_seat_climate_request",
            "VehicleSpecific.remote_auto_seat_climate_request",
        ),
        (
            "auto_steering_wheel_heater",
            "VehicleSpecific.remote_auto_steering_wheel_heat_climate_request",
            "VehicleSpecific.remote_auto_steering_wheel_heat_climate_request",
        ),
        (
            "defrost",
            "VehicleSpecific.set_preconditioning_max",
            "VehicleSpecific.set_preconditioning_max",
        ),
        (
            "allow_charging_from_grid",
            "EnergySpecific.storm_mode",
            "EnergySpecific.storm_mode",
        ),
        (
            "storm_mode",
            "EnergySpecific.grid_import_export",
            "EnergySpecific.grid_import_export",
        ),
        (
            "sentry_mode",
            "VehicleSpecific.set_sentry_mode",
            "VehicleSpecific.set_sentry_mode",
        ),
        (
            "valet_mode",
            "VehicleSpecific.set_valet_mode",
            "VehicleSpecific.set_valet_mode",
        ),
    ],
)
async def test_switch_services(hass: HomeAssistant, name, on, off) -> None:
    """Tests that the switch services work."""

    await setup_platform(hass, [Platform.SWITCH])

    entity_id = f"switch.test_{name}"
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
