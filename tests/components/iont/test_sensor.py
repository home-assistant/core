"""Tests for the IONT sensor entities."""

import math
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ServerDeviceFailureError
from modbus_connection.encode import encode_float32
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iont.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import STATUS_REGISTER, connector_base, seed_dc_charger, setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

POWER_ENTITY = "sensor.connector_1_power"
TOTAL_ENERGY_ENTITY = "sensor.connector_1_total_energy"
TOTAL_ENERGY_REGISTER = connector_base(1) + 0x24


async def _setup_sensor_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch("homeassistant.components.iont.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, entry)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    snapshot: SnapshotAssertion,
) -> None:
    """All sensor entities and their states match the snapshot."""
    seed_dc_charger(mock_modbus_unit)
    await _setup_sensor_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_diagnostic_tail_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The niche diagnostic points stay out of the way until asked for."""
    await _setup_sensor_platform(hass, mock_config_entry)

    # What a driver looks at is there from the start.
    assert hass.states.get(POWER_ENTITY) is not None
    assert hass.states.get("sensor.connector_1_charging_state") is not None
    assert hass.states.get("sensor.iont_charger_available_power") is not None

    for entity_id in (
        "sensor.connector_1_voltage_l1",
        "sensor.connector_1_frequency_l1",
        "sensor.connector_1_inner_temperature",
        "sensor.iont_charger_main_breaker_current",
        "sensor.iont_charger_uptime",
    ):
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_battery_only_on_a_dc_connector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Only a DC connector knows the vehicle's state of charge."""
    seed_dc_charger(mock_modbus_unit)
    await _setup_sensor_platform(hass, mock_config_entry)

    assert hass.states.get("sensor.connector_1_battery") is None
    state = hass.states.get("sensor.connector_2_battery")
    assert state is not None
    assert state.state == "74.5"


async def test_unknown_status_reads_as_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The charger's "unknown" code, and a code this integration has no name for."""
    mock_modbus_unit.input[STATUS_REGISTER] = 0
    await _setup_sensor_platform(hass, mock_config_entry)

    state = hass.states.get("sensor.iont_charger_status")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensors_unavailable_on_a_dead_link(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A failed refresh marks the sensors unavailable, except the total."""
    await _setup_sensor_platform(hass, mock_config_entry)

    total = hass.states.get(TOTAL_ENERGY_ENTITY)
    assert total is not None
    assert total.state == "1234.567"  # kWh

    mock_modbus_unit.fail_requests(ModbusConnectionError("link died"))

    await _tick(hass, freezer)

    assert hass.states.get(POWER_ENTITY).state == STATE_UNAVAILABLE
    # A long-term statistic holds its last value while the charger is offline.
    assert hass.states.get(TOTAL_ENERGY_ENTITY).state == "1234.567"


async def test_total_energy_ignores_a_small_dip(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A reading slightly below the last total is a glitch, a large drop is a reset."""
    await _setup_sensor_platform(hass, mock_config_entry)

    mock_modbus_unit.input[TOTAL_ENERGY_REGISTER] = encode_float32(1234000.0)
    await _tick(hass, freezer)
    assert hass.states.get(TOTAL_ENERGY_ENTITY).state == "1234.567"

    # A reading the charger has no value for is not a total either.
    mock_modbus_unit.input[TOTAL_ENERGY_REGISTER] = encode_float32(math.nan)
    await _tick(hass, freezer)
    assert hass.states.get(TOTAL_ENERGY_ENTITY).state == "1234.567"

    mock_modbus_unit.input[TOTAL_ENERGY_REGISTER] = encode_float32(1000.0)
    await _tick(hass, freezer)
    assert hass.states.get(TOTAL_ENERGY_ENTITY).state == "1.0"

    mock_modbus_unit.input[TOTAL_ENERGY_REGISTER] = encode_float32(2000.0)
    await _tick(hass, freezer)
    assert hass.states.get(TOTAL_ENERGY_ENTITY).state == "2.0"


async def test_total_energy_restored_when_the_charger_is_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The last total survives a restart while the charger has not answered yet."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(TOTAL_ENERGY_ENTITY, "999.999"),
                {"native_value": 999999, "native_unit_of_measurement": "Wh"},
            ),
        ),
    )
    # The charger answers for itself, but the connector does not.
    mock_modbus_unit.fail_read(
        connector_base(1), ServerDeviceFailureError(), register_type="input"
    )

    await _setup_sensor_platform(hass, mock_config_entry)

    assert hass.states.get(POWER_ENTITY).state == STATE_UNAVAILABLE
    state = hass.states.get(TOTAL_ENERGY_ENTITY)
    assert state is not None
    assert state.state == "999.999"
