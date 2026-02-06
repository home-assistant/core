"""Test the Teslemetry sensor platform."""

from copy import deepcopy
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import ENERGY_HISTORY, ENERGY_HISTORY_EMPTY, VEHICLE_DATA, VEHICLE_DATA_ALT

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_streaming_charge_energy_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_add_listener: AsyncMock,
) -> None:
    """Test reset detection for streaming charge energy sensors."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    await setup_platform(hass, [Platform.SENSOR])
    vin = VEHICLE_DATA_ALT["response"]["vin"]
    entity_id = "sensor.test_charge_energy_added"

    # Send initial value
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 10.0}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "10.0"
    assert state.attributes.get("last_reset") is None

    # Small correction (< 1 kWh) should NOT trigger reset
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 9.5}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "9.5"
    assert state.attributes.get("last_reset") is None

    # Value increase should NOT trigger reset
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 15.0}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "15.0"
    assert state.attributes.get("last_reset") is None

    # Drop to 0 should trigger reset
    freezer.move_to("2024-01-01 01:00:00+00:00")
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 0}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "0"
    assert state.attributes.get("last_reset") is not None

    # Large drop (> 1 kWh) should trigger reset
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 20.0}})
    await hass.async_block_till_done()

    freezer.move_to("2024-01-01 02:00:00+00:00")
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 5.0}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "5.0"
    assert state.attributes["last_reset"] == "2024-01-01T02:00:00+00:00"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_streaming_charge_energy_restore_last_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_add_listener: AsyncMock,
) -> None:
    """Test that last_reset is restored after reload for streaming sensors."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    entry = await setup_platform(hass, [Platform.SENSOR])
    vin = VEHICLE_DATA_ALT["response"]["vin"]
    entity_id = "sensor.test_charge_energy_added"

    # Set initial value then trigger reset
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 10.0}})
    await hass.async_block_till_done()

    freezer.move_to("2024-01-01 01:00:00+00:00")
    mock_add_listener.send({"vin": vin, "data": {Signal.AC_CHARGING_ENERGY_IN: 0}})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["last_reset"] == "2024-01-01T01:00:00+00:00"

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # last_reset should be restored
    state = hass.states.get(entity_id)
    assert state.attributes["last_reset"] == "2024-01-01T01:00:00+00:00"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_polling_charge_energy_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Test reset detection for polling charge energy sensors."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Set initial charge_energy_added to 10
    initial_data = deepcopy(VEHICLE_DATA)
    initial_data["response"]["charge_state"]["charge_energy_added"] = 10.0
    mock_vehicle_data.return_value = initial_data
    await setup_platform(hass, [Platform.SENSOR])
    entity_id = "sensor.test_charge_energy_added"

    state = hass.states.get(entity_id)
    assert state.state == "10.0"
    assert state.attributes.get("last_reset") is None

    # Small correction should NOT trigger reset
    correction_data = deepcopy(VEHICLE_DATA)
    correction_data["response"]["charge_state"]["charge_energy_added"] = 9.5
    mock_vehicle_data.return_value = correction_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "9.5"
    assert state.attributes.get("last_reset") is None

    # Drop to 0 should trigger reset
    freezer.move_to("2024-01-01 01:00:00+00:00")
    reset_data = deepcopy(VEHICLE_DATA)
    reset_data["response"]["charge_state"]["charge_energy_added"] = 0
    mock_vehicle_data.return_value = reset_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0"
    assert state.attributes.get("last_reset") is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_history_last_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Test that energy history sensors have last_reset from period start."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "sensor.energy_site_battery_discharged"

    # Trigger coordinator refresh to populate data
    mock_energy_history.return_value = ENERGY_HISTORY
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    # The first timestamp in the fixture is "2024-09-18T00:00:00+10:00"
    assert state.attributes.get("last_reset") == "2024-09-18T00:00:00+10:00"
