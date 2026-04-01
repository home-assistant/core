"""Test the Teslemetry switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.teslemetry.const import (
    DOMAIN,
    LABS_CHARGE_ON_SOLAR_FEATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import assert_entities, assert_entities_alt, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


async def _async_enable_charge_on_solar_preview_feature(hass: HomeAssistant) -> None:
    """Enable the Teslemetry charge-on-solar preview feature."""
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE, True)


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

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("switch.test_sentry_mode").state == STATE_ON
    assert hass.states.get("switch.test_auto_seat_climate_left").state == STATE_ON
    assert hass.states.get("switch.test_auto_seat_climate_right").state == STATE_OFF
    assert hass.states.get("switch.test_auto_steering_wheel_heater").state == STATE_ON
    assert hass.states.get("switch.test_defrost").state == STATE_OFF
    assert hass.states.get("switch.test_charge").state == STATE_ON


async def test_charge_on_solar_switch_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    """Test charge-on-solar switch is disabled by default."""
    await setup_platform(hass, [Platform.SWITCH])

    assert hass.states.get("switch.test_charge_on_solar") is None


async def test_charge_on_solar_switch_enabled_by_labs(
    hass: HomeAssistant,
) -> None:
    """Test charge-on-solar switch appears when Labs feature is enabled."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    await setup_platform(hass, [Platform.SWITCH])

    assert (state := hass.states.get("switch.test_charge_on_solar")) is not None
    assert state.attributes["assumed_state"] is True


@pytest.mark.parametrize(
    ("service", "enabled", "expected_state"),
    [
        (SERVICE_TURN_ON, True, STATE_ON),
        (SERVICE_TURN_OFF, False, STATE_OFF),
    ],
)
async def test_charge_on_solar_switch_services(
    hass: HomeAssistant,
    service: str,
    enabled: bool,
    expected_state: str,
) -> None:
    """Test charge-on-solar switch service calls."""
    await _async_enable_charge_on_solar_preview_feature(hass)

    with patch("teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc") as (
        listener
    ):
        listener.return_value = lambda: None
        entry = await setup_platform(hass, [Platform.SWITCH])

        for call in listener.call_args_list:
            call.args[0](91)

        with patch(
            "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
            return_value=COMMAND_OK,
        ) as command:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: "switch.test_charge_on_solar"},
                blocking=True,
            )
            command.assert_called_once_with(
                enabled=enabled,
                lower_charge_limit=30,
                upper_charge_limit=91,
            )

        assert (state := hass.states.get("switch.test_charge_on_solar")) is not None
        assert state.state == expected_state
        assert state.attributes["assumed_state"] is True

        await reload_platform(hass, entry, [Platform.SWITCH])

        assert (restored := hass.states.get("switch.test_charge_on_solar")) is not None
        assert restored.state == expected_state
        assert restored.attributes["assumed_state"] is True


async def test_disable_charge_on_solar_preview_removes_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling preview removes charge-on-solar switch from entity registry."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    entry = await setup_platform(hass, [Platform.SWITCH])

    assert entity_registry.async_get("switch.test_charge_on_solar") is not None

    with patch.object(hass.config_entries, "async_schedule_reload"):
        await async_update_preview_feature(
            hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE, False
        )
        await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.SWITCH])

    assert entity_registry.async_get("switch.test_charge_on_solar") is None
