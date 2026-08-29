"""Tests for the SolarEdge Modbus sensor entities."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.solaredge_modbus.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import add_second_meter

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

LIFETIME_ENERGY_ENTITY = "sensor.solaredge_se10000h_energy"


async def _setup_sensor_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch(
        "homeassistant.components.solaredge_modbus.PLATFORMS", [Platform.SENSOR]
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All sensor entities and their states match the snapshot."""
    await _setup_sensor_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_diagnostic_tail_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The niche diagnostic points stay out of the way until asked for."""
    await _setup_sensor_platform(hass, mock_config_entry)

    # What a solar owner looks at is there from the start.
    assert hass.states.get("sensor.solaredge_se10000h_power") is not None

    for entity_id in (
        "sensor.solaredge_se10000h_apparent_power",
        "sensor.solaredge_se10000h_frequency",
        # Voltage barely moves and there is a lot of it; ask for it if you want it.
        "sensor.solaredge_se10000h_voltage",
        "sensor.solaredge_se10000h_dc_voltage",
    ):
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_sensors_unavailable_on_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A failed refresh marks the sensor entities unavailable."""
    await _setup_sensor_platform(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_se10000h_power")
    assert state is not None
    assert state.state == "9490"

    # The device stops answering reads of the inverter block.
    mock_modbus_unit.fail_read(40069, ModbusTimeoutError("timed out"))

    await _tick(hass, freezer)

    state = hass.states.get("sensor.solaredge_se10000h_power")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # ...and comes back once the inverter answers again.
    mock_modbus_unit.fail_read(40069, None)

    await _tick(hass, freezer)

    state = hass.states.get("sensor.solaredge_se10000h_power")
    assert state is not None
    assert state.state == "9490"


async def test_no_phase_currents_on_single_phase(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A single-phase inverter gets a total current sensor, but no phase ones."""
    await _setup_sensor_platform(hass, mock_config_entry)

    assert hass.states.get("sensor.solaredge_se10000h_current") is not None
    assert hass.states.get("sensor.solaredge_se10000h_current_phase_a") is None


async def test_phase_currents_on_three_phase(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A three-phase inverter gets per-phase current sensors."""
    mock_modbus_unit.holding[40069] = 103  # SunSpec three-phase inverter model

    await _setup_sensor_platform(hass, mock_config_entry)

    assert hass.states.get("sensor.solaredge_se10000h_current_phase_a") is not None
    assert hass.states.get("sensor.solaredge_se10000h_current_phase_b") is not None
    assert hass.states.get("sensor.solaredge_se10000h_current_phase_c") is not None


async def test_two_meters_are_told_apart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A second meter reads its own block and goes unavailable on its own.

    Both meters report the same measurements here, so what is worth proving is
    that each entity reaches the meter it belongs to: the values move apart
    when one block does, and only that meter's entities go unavailable when it
    stops answering.
    """
    add_second_meter(mock_modbus_unit, "7E5B22D3")

    await _setup_sensor_platform(hass, mock_config_entry)

    first = hass.states.get("sensor.meter_1_power")
    second = hass.states.get("sensor.meter_2_power")
    assert first is not None
    assert second is not None
    assert first.state == second.state

    # Only the second meter's power register moves.
    mock_modbus_unit.holding[40206 + 174] = 1000

    await _tick(hass, freezer)

    assert hass.states.get("sensor.meter_1_power") == first
    second = hass.states.get("sensor.meter_2_power")
    assert second is not None
    assert second.state != first.state

    # Only the second meter falls silent.
    mock_modbus_unit.fail_read(40297, ModbusTimeoutError("timed out"))

    await _tick(hass, freezer)
    await _tick(hass, freezer)

    assert hass.states.get("sensor.meter_2_power").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.meter_1_power").state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_delta_meter_measures_nothing_against_a_neutral(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A delta meter has no neutral, so no voltage is measured against one."""
    mock_modbus_unit.holding[40188] = 204  # SunSpec three-phase delta meter

    await _setup_sensor_platform(hass, mock_config_entry)

    # Line-to-line is all a delta meter has.
    assert hass.states.get("sensor.meter_1_voltage_phase_a_b") is not None
    assert hass.states.get("sensor.meter_1_voltage_phase_b_c") is not None

    assert hass.states.get("sensor.meter_1_voltage") is None
    assert hass.states.get("sensor.meter_1_voltage_phase_a_n") is None
    assert hass.states.get("sensor.meter_1_voltage_phase_b_n") is None
    assert hass.states.get("sensor.meter_1_voltage_phase_c_n") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_split_phase_meter_has_two_phases(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A split-phase meter measures two phases, so the third is not offered."""
    mock_modbus_unit.holding[40188] = 202  # SunSpec split-phase meter

    await _setup_sensor_platform(hass, mock_config_entry)

    assert hass.states.get("sensor.meter_1_power_phase_a") is not None
    assert hass.states.get("sensor.meter_1_power_phase_b") is not None
    assert hass.states.get("sensor.meter_1_voltage_phase_a_n") is not None

    assert hass.states.get("sensor.meter_1_power_phase_c") is None
    assert hass.states.get("sensor.meter_1_voltage_phase_c_n") is None
    assert hass.states.get("sensor.meter_1_voltage_phase_b_c") is None


async def test_meter_energy_ignores_transient_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter accumulator transiently reporting zero is held at the last maximum."""
    await _setup_sensor_platform(hass, mock_config_entry)

    state = hass.states.get("sensor.meter_1_energy_exported")
    assert state is not None
    initial = float(state.state)
    assert initial > 0

    # The meter block transiently reports "not accumulated" (zero).
    mock_modbus_unit.holding[40226] = 0
    mock_modbus_unit.holding[40227] = 0

    await _tick(hass, freezer)

    state = hass.states.get("sensor.meter_1_energy_exported")
    assert state is not None
    assert float(state.state) == initial


async def test_lifetime_energy_never_goes_backwards(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A transiently lower lifetime energy reading is held at the last maximum."""
    await _setup_sensor_platform(hass, mock_config_entry)

    state = hass.states.get(LIFETIME_ENERGY_ENTITY)
    assert state is not None
    initial = float(state.state)

    # The inverter transiently reports 0 ("not accumulated", decodes to None);
    # the sensor holds the last maximum instead of going unknown.
    mock_modbus_unit.holding[40093] = 0
    mock_modbus_unit.holding[40094] = 0

    await _tick(hass, freezer)

    state = hass.states.get(LIFETIME_ENERGY_ENTITY)
    assert state is not None
    assert float(state.state) == initial

    # The inverter glitches and reports a far lower lifetime energy.
    mock_modbus_unit.holding[40093] = 0
    mock_modbus_unit.holding[40094] = 1000

    await _tick(hass, freezer)

    state = hass.states.get(LIFETIME_ENERGY_ENTITY)
    assert state is not None
    assert float(state.state) == initial
    assert "lower than" in caplog.text

    # The inverter recovers with a higher value; the sensor follows again.
    mock_modbus_unit.holding[40093] = 0x1000
    mock_modbus_unit.holding[40094] = 0

    await _tick(hass, freezer)

    state = hass.states.get(LIFETIME_ENERGY_ENTITY)
    assert state is not None
    assert float(state.state) > initial


async def test_lifetime_energy_restored_after_restart(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The last seen maximum survives a restart and beats a lower device reading."""
    # A previous run saw a higher lifetime energy than the device reports now.
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(LIFETIME_ENERGY_ENTITY, "99999.999"),
                {
                    "native_value": 99999999,
                    "native_unit_of_measurement": "Wh",
                },
            ),
        ),
    )

    await _setup_sensor_platform(hass, mock_config_entry)

    state = hass.states.get(LIFETIME_ENERGY_ENTITY)
    assert state is not None
    assert float(state.state) == 99999.999  # kWh, from the restored maximum
