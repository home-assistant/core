"""Tests for the SolarEdge Modbus config-entry setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusTimeoutError,
    ServerDeviceFailureError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.solaredge_modbus.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL_NUMBER, async_seed_unit, tcp_data

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


async def test_meter_is_a_sub_device_of_the_inverter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A meter is real hardware of its own, hanging off the inverter."""
    await _setup(hass, mock_config_entry)

    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
    )
    assert inverter is not None

    meter = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{SERIAL_NUMBER}_meter_1"), mock_config_entry.entry_id
    )
    assert meter is not None
    assert meter.via_device_id == inverter.id
    assert meter.name == "Meter 1"
    assert meter.model == "SE-MTR-3Y-400V-A"


async def test_meter_that_left_the_installation_is_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter taken off the inverter does not linger as a device.

    Which meters are attached is read while the entry is set up, so a meter
    that was removed is gone by the time the entry loads again.
    """
    await _setup(hass, mock_config_entry)

    meter_identifier = (DOMAIN, f"{SERIAL_NUMBER}_meter_1")
    assert (
        device_registry.async_get_device_by_identifier(
            meter_identifier, mock_config_entry.entry_id
        )
        is not None
    )

    mock_modbus_unit.fail_read(40188, IllegalDataAddressError())

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            meter_identifier, mock_config_entry.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
        )
        is not None
    )


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


async def test_another_inverter_on_the_address_fails_the_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An address that moves to another inverter stops feeding these entities.

    Setting up checks the serial number, but the entry keeps polling an
    address, and a lease handed out again can put a different inverter behind
    it. Its production is not this entry's, whatever the entities are named
    after.
    """
    await _setup(hass, mock_config_entry)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await async_seed_unit(
        hass, mock_modbus_unit, serial_registers=[20308, 18501, 21041, 12851]
    )

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


@pytest.mark.parametrize(
    "serial_registers",
    [
        pytest.param([20308, 18501, 21041, 12851], id="another inverter"),
        pytest.param([0, 0, 0, 0], id="no serial number"),
    ],
)
async def test_setup_error_when_the_identity_does_not_match(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    serial_registers: list[int],
) -> None:
    """An address that no longer holds this inverter must not adopt its data.

    Every identity in this integration derives from the entry's serial number,
    so loading a device that reports another one, or none at all, would hang
    this entry's name and history on the wrong inverter.
    """
    await async_seed_unit(
        hass, mock_modbus_connection.for_unit(2), serial_registers=serial_registers
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id=SERIAL_NUMBER,
        data=tcp_data(unit_id=2),
    )

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retry_when_the_identity_is_unreadable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A poll without the identity block proves nothing, so setup tries again.

    The rest of the device can answer perfectly well while the identity block
    does not, and accepting the entry then would skip the check that this is
    still the same inverter. A device fault says exactly that, where silence
    from the first block on would mean a dead link.
    """
    mock_modbus_unit.fail_read(40004, ServerDeviceFailureError())

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_the_measurements_are_unreadable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A first poll without the inverter block would cost the phase entities.

    Which entities exist is decided once, from the inverter's DID, and without
    it none of the phase measurements match. An entry accepted here would be
    missing those entities until a reload, however well the inverter answers
    after that.
    """
    mock_modbus_unit.fail_read(40069, ServerDeviceFailureError())

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
