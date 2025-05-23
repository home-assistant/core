"""Test the tesla_fleet switch platform."""

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry


async def test_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the switch entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.SWITCH])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_switch_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the switch entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, normal_config_entry, [Platform.SWITCH])
    assert_entities_alt(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_switch_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the switch entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, normal_config_entry, [Platform.SWITCH])
    state = hass.states.get("switch.test_auto_seat_climate_left")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("name", "on", "off"),
    [
        ("test_charge", "VehicleFleet.charge_start", "VehicleFleet.charge_stop"),
        (
            "test_auto_seat_climate_left",
            "VehicleFleet.remote_auto_seat_climate_request",
            "VehicleFleet.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_seat_climate_right",
            "VehicleFleet.remote_auto_seat_climate_request",
            "VehicleFleet.remote_auto_seat_climate_request",
        ),
        (
            "test_auto_steering_wheel_heater",
            "VehicleFleet.remote_auto_steering_wheel_heat_climate_request",
            "VehicleFleet.remote_auto_steering_wheel_heat_climate_request",
        ),
        (
            "test_defrost",
            "VehicleFleet.set_preconditioning_max",
            "VehicleFleet.set_preconditioning_max",
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
            "VehicleFleet.set_sentry_mode",
            "VehicleFleet.set_sentry_mode",
        ),
    ],
)
async def test_switch_services(
    hass: HomeAssistant,
    name: str,
    on: str,
    off: str,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the switch service calls work."""

    await setup_platform(hass, normal_config_entry, [Platform.SWITCH])

    entity_id = f"switch.{name}"
    with patch(
        f"tesla_fleet_api.tesla.{on}",
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
        f"tesla_fleet_api.tesla.{off}",
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


async def test_switch_no_scope(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    readonly_config_entry: MockConfigEntry,
) -> None:
    """Tests that the switch entities are correct."""

    await setup_platform(hass, readonly_config_entry, [Platform.SWITCH])
    with pytest.raises(ServiceValidationError, match="Missing vehicle commands scope"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_auto_steering_wheel_heater"},
            blocking=True,
        )
