"""Test the Teslemetry sensor platform."""

from copy import deepcopy
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import DistanceConverter

from . import assert_entities, assert_entities_alt, setup_platform
from .const import ENERGY_HISTORY_EMPTY, VEHICLE_DATA, VEHICLE_DATA_ALT

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
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

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
    assert hass.states.get("sensor.teslemetry_credits").state == "1980"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_total_increasing_clamp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Test that polling TOTAL_INCREASING sensors clamp small backwards jitter.

    The Tesla Fleet API occasionally returns a value slightly below the
    previous reading due to floating-point jitter or server-side
    recalculation. Recorder emits a warning and resets the statistics
    baseline in that case. The sensor platform must clamp such decreases
    to the last seen maximum while still forwarding a real drop to zero
    (meter cycle) so the statistics engine keeps working as expected.
    Regression test for home-assistant/core#159988.
    """
    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Odometer native unit is miles; HA converts to km by default in tests.
    def miles_to_km(miles: float) -> float:
        return DistanceConverter.convert(
            miles, UnitOfLength.MILES, UnitOfLength.KILOMETERS
        )

    # Seed initial odometer value
    initial_data = deepcopy(VEHICLE_DATA)
    initial_data["response"]["vehicle_state"]["odometer"] = 6481.02
    mock_vehicle_data.return_value = initial_data
    await setup_platform(hass, [Platform.SENSOR])
    entity_id = "sensor.test_odometer"

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(miles_to_km(6481.02))

    # Tiny backwards jitter must be clamped to the previous value
    jitter_data = deepcopy(VEHICLE_DATA)
    jitter_data["response"]["vehicle_state"]["odometer"] = 6481.01
    mock_vehicle_data.return_value = jitter_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert float(state.state) == pytest.approx(miles_to_km(6481.02))

    # Strictly larger reading passes through and becomes the new baseline
    forward_data = deepcopy(VEHICLE_DATA)
    forward_data["response"]["vehicle_state"]["odometer"] = 6482.5
    mock_vehicle_data.return_value = forward_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert float(state.state) == pytest.approx(miles_to_km(6482.5))

    # A real meter reset to zero must pass through so statistics detects cycles
    reset_data = deepcopy(VEHICLE_DATA)
    reset_data["response"]["vehicle_state"]["odometer"] = 0
    mock_vehicle_data.return_value = reset_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0.0"


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
