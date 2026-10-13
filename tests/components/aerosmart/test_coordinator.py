"""Tests for the aerosmart coordinator."""

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusConnectionError
from modbus_connection.mock import MockModbusUnit

from homeassistant.components.aerosmart.const import READINGS_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_failed_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A Modbus read failure fails the update and makes entities unavailable.

    ``mock_modbus_unit_ventilation`` is the same ``MockModbusUnit`` instance
    the coordinator's ``AerosmartDevice`` was built from (both resolve
    through the same ``mock_modbus_connection``), so mutating its store here
    affects the very unit the integration under test reads.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    runtime = mock_config_entry.runtime_data
    coordinator = runtime.readings
    assert coordinator.last_update_success is True

    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )

    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    outside = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
    assert outside is not None
    assert outside.state == STATE_UNAVAILABLE

    # The independent settings poll has not been invalidated by this refresh.
    assert runtime.settings.last_update_success is True


async def test_recovers_after_transient_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A subsequent successful poll clears the failure again."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    coordinator = mock_config_entry.runtime_data.readings
    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False

    mock_modbus_unit_ventilation.fail_requests(None)
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    outside = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
    assert outside.state == "0.123"


async def test_partial_failure_only_marks_its_subsystem_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One refused component keeps unrelated fresh data available."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    coordinator = mock_config_entry.runtime_data.readings
    mock_modbus_unit_ventilation.fail_read(230, IllegalDataAddressError())

    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert "carbon_dioxide" in coordinator.data.failed

    co2 = hass.states.get("sensor.aerosmart_co2")
    outside = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
    assert co2 is not None
    assert co2.state == STATE_UNAVAILABLE
    assert outside is not None
    assert outside.state == "0.123"
