"""Tests for the BLUETTI Modbus config-entry setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import AcknowledgeError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit

from homeassistant.components.bluetti_modbus.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed

VOLTAGE_ENTITY = "sensor.balco260_battery_voltage"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, produces entities, and unloads cleanly."""
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(VOLTAGE_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_serial_number_is_device_metadata_not_a_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The serial number shows up as device info, not a plain sensor entity."""
    await _setup(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.serial_number == SERIAL

    assert hass.states.get("sensor.balco260_serial_number") is None


async def test_firmware_versions_are_device_metadata_not_a_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """ARM/DSP firmware versions show up as device info, not sensor entities."""
    await _setup(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.sw_version == "ARM 0, DSP 0"

    assert hass.states.get("sensor.balco260_arm_firmware_version") is None
    assert hass.states.get("sensor.balco260_dsp_firmware_version") is None


async def test_setup_retry_when_device_unresponsive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that answers nothing puts the entry in setup retry."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_when_link_settings_are_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Another integration holding the device on other link settings is fatal."""
    with patch(
        "homeassistant.components.bluetti_modbus.async_get_unit",
        side_effect=HomeAssistantError("already in use with different link settings"),
    ):
        await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_dead_link_fails_the_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that stops answering after setup goes unavailable, then recovers."""
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick(hass, freezer)

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is False

    state = hass.states.get(VOLTAGE_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_modbus_unit.fail_requests(None)
    await _tick(hass, freezer)

    state = hass.states.get(VOLTAGE_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_transient_busy_response_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that asks for a retry once does not fail the refresh."""
    read_holding_registers = mock_modbus_unit.read_holding_registers
    attempts = 0

    async def busy_once(address: int, count: int) -> list[int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AcknowledgeError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", busy_once):
        await _setup(hass, mock_config_entry)

    assert attempts > 1  # the retry really happened
    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(VOLTAGE_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_dead_link_on_the_retry_still_fails_the_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that goes fully silent right after asking for a retry still fails."""
    attempts = 0

    async def busy_then_dead(address: int, count: int) -> list[int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AcknowledgeError
        raise ModbusTimeoutError("link died")

    with patch.object(mock_modbus_unit, "read_holding_registers", busy_then_dead):
        await _setup(hass, mock_config_entry)

    assert attempts > 1  # the retry really happened
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_identity_mismatch_after_setup_fails_the_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An address reassigned to a different device stops updating, not just goes stale."""
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.holding[50206] = 1  # a different serial answers now
    await _tick(hass, freezer)

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is False

    state = hass.states.get(VOLTAGE_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_excluded_fields_are_dropped_from_the_read_plan(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A field with no entity yet is not polled either, not just not created."""
    await _setup(hass, mock_config_entry)

    device = mock_config_entry.runtime_data.coordinator.device
    assert device.get_field("ac_o_switch") is None
