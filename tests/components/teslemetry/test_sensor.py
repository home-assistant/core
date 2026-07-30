"""Test the Teslemetry sensor platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
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
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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
                Signal.LIFETIME_ENERGY_GAINED_REGEN: 1234.5,
                Signal.MILES_SINCE_RESET: 678.9,
                Signal.SELF_DRIVING_MILES_SINCE_RESET: 123.4,
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

    assert (regen := hass.states.get("sensor.test_lifetime_energy_gained_regen"))
    assert regen.state == "1234.5"
    assert regen.attributes["device_class"] == "energy"
    assert regen.attributes["state_class"] == "total_increasing"
    assert regen.attributes["unit_of_measurement"] == "kWh"

    # Distance sensors are declared in native miles, HA displays them in the
    # hass unit system's default (km in tests).
    assert (miles := hass.states.get("sensor.test_miles_since_reset"))
    assert miles.state == "1092.5836416"
    assert miles.attributes["device_class"] == "distance"
    assert miles.attributes["state_class"] == "total_increasing"
    assert miles.attributes["unit_of_measurement"] == "km"

    assert (fsd_miles := hass.states.get("sensor.test_self_driving_miles_since_reset"))
    assert fsd_miles.state == "198.5930496"
    assert fsd_miles.attributes["device_class"] == "distance"
    assert fsd_miles.attributes["state_class"] == "total_increasing"
    assert fsd_miles.attributes["unit_of_measurement"] == "km"

    assert [
        entity_registry.async_get(entity_id)
        for entity_id in (
            "sensor.test_lifetime_energy_gained_regen",
            "sensor.test_miles_since_reset",
            "sensor.test_self_driving_miles_since_reset",
        )
    ] == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(
            "sensor.test_lifetime_energy_gained_regen",
            id="lifetime_energy_gained_regen",
        ),
        pytest.param("sensor.test_miles_since_reset", id="miles_since_reset"),
        pytest.param(
            "sensor.test_self_driving_miles_since_reset",
            id="self_driving_miles_since_reset",
        ),
    ],
)
async def test_new_streaming_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_add_listener: AsyncMock,
    entity_id: str,
) -> None:
    """Test the new firmware-2025.44 streaming sensors are disabled-by-default diagnostics."""

    await setup_platform(hass, [Platform.SENSOR])

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


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
