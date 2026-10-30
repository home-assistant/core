"""Tests for the aerosmart coordinator."""

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.aerosmart.const import DOMAIN, READINGS_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_device_info_includes_model_and_software_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """Device metadata is included when the controller provides it."""
    mock_modbus_unit_ventilation.holding[5000] = [0, 3]
    mock_modbus_unit_ventilation.holding[1156] = [0, 42]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "3"
    assert device.sw_version == "42"


async def test_device_info_recovers_after_initial_general_failure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """Device metadata is updated when the general subsystem recovers."""
    mock_modbus_unit_ventilation.fail_read(
        5000, ModbusTimeoutError("simulated general subsystem timeout")
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model is None
    assert device.sw_version is None

    mock_modbus_unit_ventilation.fail_read(5000, None)
    mock_modbus_unit_ventilation.holding[5000] = [0, 3]
    mock_modbus_unit_ventilation.holding[1156] = [0, 42]
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.model == "3"
    assert device.sw_version == "42"


async def test_update_failed_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A Modbus read failure makes entities unavailable."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )

    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    outside = hass.states.get("sensor.aerosmart_outdoor_air_temperature")
    assert outside is not None
    assert outside.state == STATE_UNAVAILABLE

    # The independent settings poll has not been invalidated by this refresh.
    filter_life = hass.states.get("sensor.aerosmart_fine_dust_filter_service_life")
    assert filter_life is not None
    assert filter_life.state == "0"


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

    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    outside = hass.states.get("sensor.aerosmart_outdoor_air_temperature")
    assert outside is not None
    assert outside.state == STATE_UNAVAILABLE

    mock_modbus_unit_ventilation.fail_requests(None)
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    outside = hass.states.get("sensor.aerosmart_outdoor_air_temperature")
    assert outside is not None
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

    mock_modbus_unit_ventilation.fail_read(230, IllegalDataAddressError())

    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    co2 = hass.states.get("sensor.aerosmart_carbon_dioxide")
    outside = hass.states.get("sensor.aerosmart_outdoor_air_temperature")
    assert co2 is not None
    assert co2.state == STATE_UNAVAILABLE
    assert outside is not None
    assert outside.state == "0.123"
