"""Test the Teslemetry switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


async def test_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the switch entities are correct."""

    entry = await setup_platform(hass, [Platform.SWITCH])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_switch_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the switch entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.SWITCH])
    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("name", "on", "off"),
    [
        ("test_charge", "Vehicle.charge_start", "Vehicle.charge_stop"),
        (
            "test_auto_seat_climate_left",
            "Vehicle.remote_auto_seat_climate_request",
            "Vehicle.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_seat_climate_right",
            "Vehicle.remote_auto_seat_climate_request",
            "Vehicle.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_steering_wheel_heater",
            "Vehicle.remote_auto_steering_wheel_heat_climate_request",
            "Vehicle.remote_auto_steering_wheel_heat_climate_request",
        ),
        (
            "test_defrost",
            "Vehicle.set_preconditioning_max",
            "Vehicle.set_preconditioning_max",
        ),
        (
            "energy_site_storm_watch",
            "EnergySite.storm_mode",
            "EnergySite.storm_mode",
        ),
        (
            "energy_site_allow_charging_from_grid",
            "EnergySite.grid_import_export",
            "EnergySite.grid_import_export",
        ),
        (
            "test_sentry_mode",
            "Vehicle.set_sentry_mode",
            "Vehicle.set_sentry_mode",
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
        f"tesla_fleet_api.teslemetry.{on}",
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
        f"tesla_fleet_api.teslemetry.{off}",
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


async def test_switch_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the switch entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.SWITCH])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SENTRY_MODE: "SentryModeStateIdle",
                Signal.AUTO_SEAT_CLIMATE_LEFT: True,
                Signal.AUTO_SEAT_CLIMATE_RIGHT: False,
                Signal.HVAC_STEERING_WHEEL_HEAT_AUTO: True,
                Signal.DEFROST_MODE: "DefrostModeStateOff",
                Signal.DETAILED_CHARGE_STATE: "DetailedChargeStateCharging",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Reload the entry
    await reload_platform(hass, entry, [Platform.SWITCH])

    # Assert the entities restored their values
    for entity_id in (
        "switch.test_sentry_mode",
        "switch.test_auto_seat_climate_left",
        "switch.test_auto_seat_climate_right",
        "switch.test_auto_steering_wheel_heater",
        "switch.test_defrost",
        "switch.test_charge",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=entity_id)
