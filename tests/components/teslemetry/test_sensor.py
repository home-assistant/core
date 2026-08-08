"""Test the Teslemetry sensor platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import ENERGY_HISTORY_EMPTY, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the sensor entities with the legacy polling are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entry = await setup_platform(hass, [Platform.SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Coordinator refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_streaming(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.SENSOR])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.DETAILED_CHARGE_STATE: "DetailedChargeStateCharging",
                Signal.BATTERY_LEVEL: 90,
                Signal.AC_CHARGING_ENERGY_IN: 10,
                Signal.AC_CHARGING_POWER: 2,
                Signal.CHARGING_CABLE_TYPE: None,
                Signal.TIME_TO_FULL_CHARGE: 0.166666667,
                Signal.MINUTES_TO_ARRIVAL: None,
            },
            "credits": {
                "type": "wake_up",
                "cost": 20,
                "name": "wake_up",
                "balance": 1980,
                "quota": {
                    "used": 212,
                    "fraction": 0.212,
                    "reset_at": "2026-07-10T00:00:00.000Z",
                },
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Balance-only credit events should not clear quota usage.
    mock_add_listener.send(
        {
            "credits": {"balance": 1980},
            "createdAt": "2024-10-04T10:45:18.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.teslemetry_command_quota_used").state == "21.2"

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("sensor.test_charging").state == "charging"
    assert hass.states.get("sensor.test_battery_level").state == "90"
    assert hass.states.get("sensor.test_charge_energy_added").state == "10"
    assert hass.states.get("sensor.test_charger_power").state == "2"
    assert hass.states.get("sensor.test_charge_cable").state == "unknown"
    assert hass.states.get("sensor.test_time_to_full_charge").state == "unknown"
    assert hass.states.get("sensor.test_time_to_arrival").state == "unknown"
    assert hass.states.get("sensor.teslemetry_command_credits").state == "1980"
    assert (quota_state := hass.states.get("sensor.teslemetry_command_quota_used"))
    assert quota_state.state == "21.2"


@pytest.mark.parametrize(
    ("key", "signal", "raw_value", "state"),
    [
        ("di_state_f", Signal.DI_STATE_F, "Standby", "standby"),
        ("di_state_r", Signal.DI_STATE_R, "Standby", "standby"),
        ("di_state_rel", Signal.DI_STATE_REL, "Standby", "standby"),
        ("di_state_rer", Signal.DI_STATE_RER, "Standby", "standby"),
        ("sentry_mode", Signal.SENTRY_MODE, "Armed", "armed"),
        (
            "forward_collision_warning",
            Signal.FORWARD_COLLISION_WARNING,
            "Average",
            "average",
        ),
        (
            "guest_mode_mobile_access_state",
            Signal.GUEST_MODE_MOBILE_ACCESS_STATE,
            "Authenticated",
            "authenticated",
        ),
        (
            "lane_departure_avoidance",
            Signal.LANE_DEPARTURE_AVOIDANCE,
            "Warning",
            "warning",
        ),
        ("powershare_status", Signal.POWERSHARE_STATUS, "Enabled", "enabled"),
        ("powershare_stop_reason", Signal.POWERSHARE_STOP_REASON, "Fault", "fault"),
        ("powershare_type", Signal.POWERSHARE_TYPE, "Home", "home"),
        (
            "scheduled_charging_mode",
            Signal.SCHEDULED_CHARGING_MODE,
            "StartAt",
            "start_at",
        ),
        ("speed_limit_warning", Signal.SPEED_LIMIT_WARNING, "Chime", "chime"),
        ("tonneau_tent_mode", Signal.TONNEAU_TENT_MODE, "Active", "active"),
        ("lights_turn_signal", Signal.LIGHTS_TURN_SIGNAL, "Left", "left"),
        ("hvac_power_state", Signal.HVAC_POWER, "On", "on"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_streaming_enum_none_clears_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    key: str,
    signal: Signal,
    raw_value: str,
    state: str,
) -> None:
    """A None streamed value must clear the entity, not leave it stale."""
    await setup_platform(hass, [Platform.SENSOR])
    vin = VEHICLE_DATA_ALT["response"]["vin"]
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{vin}-{key}")
    assert entity_id is not None

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {signal: raw_value},
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == state

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {signal: None},
            "createdAt": "2024-10-04T10:45:18.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_energy_history_no_time_series(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """Test energy history coordinator when time_series is not a list."""
    # Mock energy history to return data without time_series as a list

    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "sensor.energy_site_battery_discharged"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    mock_energy_history.return_value = ENERGY_HISTORY_EMPTY

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
