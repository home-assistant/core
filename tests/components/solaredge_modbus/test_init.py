"""Tests for the SolarEdge Modbus config-entry setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from homeassistant.components.solaredge_modbus.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL_NUMBER, tcp_data

from tests.common import MockConfigEntry, async_fire_time_changed

POWER_ENTITY = "sensor.solaredge_se10000h_power"

# An address inside the inverter's read, to make that read fail.
INVERTER_REGISTER = 40069


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

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == "9490"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_inverter_that_does_not_name_itself(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device is still readable when the model string comes back empty."""
    mock_modbus_unit.holding.update(dict.fromkeys(range(40020, 40036), 0))

    await _setup(hass, mock_config_entry)

    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
    )
    assert inverter is not None
    assert inverter.name == "SolarEdge inverter"
    assert inverter.model is None
    assert inverter.model_id is None


async def test_single_late_answer_is_retried(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """One missed read gets a second chance before the entities go unavailable."""
    await _setup(hass, mock_config_entry)

    read_holding_registers = mock_modbus_unit.read_holding_registers
    missed: list[int] = []

    async def miss_the_inverter_once(address: int, count: int) -> list[int]:
        """Time out on the first read covering the inverter, then behave."""
        if not missed and address <= INVERTER_REGISTER < address + count:
            missed.append(address)
            raise ModbusTimeoutError("timed out")
        return await read_holding_registers(address, count)

    with patch.object(
        mock_modbus_unit, "read_holding_registers", miss_the_inverter_once
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert missed  # the read really did fail

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_dead_link_fails_the_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that answers nothing at all fails the poll outright.

    A partial poll leaves what answered alone, but silence from end to end is
    a dead link, and every value the entry can show is then stale.
    """
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.readings.last_update_success is False

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_setup_retry_when_device_unresponsive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that does not answer puts the entry in setup retry."""
    mock_modbus_unit.fail_read(40000, ModbusTimeoutError("timed out"))

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_when_not_a_solaredge_device(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """A device without a SunSpec header fails setup permanently."""
    unit = mock_modbus_connection.for_unit(2)
    unit.holding.update(dict.fromkeys(range(40000, 40004), 0))

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id=SERIAL_NUMBER,
        data=tcp_data(unit_id=2),
    )

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_error_when_another_inverter_answers(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An address that now holds a different inverter must not adopt its data.

    Every identity in this integration derives from the entry's serial number,
    so loading a different device would hang this entry's name and history on
    the wrong inverter.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id="OTHER123",
        data=tcp_data(),
    )

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_retry_that_finds_nothing_keeps_the_first_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A link that drops during the retry does not fail the whole refresh.

    The first attempt got the identity block a second ago. Failing the refresh
    because the retry found a dead link would throw that away, and every
    sub-system that did answer with it.
    """
    await _setup(hass, mock_config_entry)

    read_holding_registers = mock_modbus_unit.read_holding_registers
    dead = False

    async def die_from_the_inverter_on(address: int, count: int) -> list[int]:
        """Go quiet at the inverter block, and stay quiet from then on."""
        nonlocal dead
        if dead or address <= INVERTER_REGISTER < address + count:
            dead = True
            raise ModbusTimeoutError("link died")
        return await read_holding_registers(address, count)

    with patch.object(
        mock_modbus_unit, "read_holding_registers", die_from_the_inverter_on
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # The identity block answered the first attempt and the refresh stands;
    # only the sub-systems that stayed silent are reported as failed.
    coordinator = mock_config_entry.runtime_data.readings
    assert coordinator.last_update_success is True
    assert coordinator.data.updated == {"common"}
    assert "inverter" in coordinator.data.failed


async def test_setup_error_when_link_settings_are_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Another integration holding the device on other line settings is fatal."""
    with patch(
        "homeassistant.components.solaredge_modbus.async_get_unit",
        side_effect=HomeAssistantError("already in use with different link settings"),
    ):
        await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
