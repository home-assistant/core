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

from .conftest import HOST, PORT, UNIT_ID, bluetti_data

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
    """A device that asks for a retry once does not fail the refresh.

    Codes 5/6 mean the device accepted the request but wants more time - the
    coordinator retries once immediately rather than treating it as a real
    failure, matching bluetti-modbus-lib's own connection-owning client.
    """
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
    """A device that goes fully silent right after asking for a retry still fails.

    The retry is one more chance for a device that is merely busy, not a
    second chance for one that has actually gone dead - a real failure there
    surfaces exactly like a first-attempt failure would.
    """
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


async def test_setup_error_when_device_type_unsupported(hass: HomeAssistant) -> None:
    """A config entry whose device type the library no longer supports is fatal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unknown",
        unique_id=f"{HOST}_{PORT}_{UNIT_ID}",
        data=bluetti_data(device_type="unknown"),
    )

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
