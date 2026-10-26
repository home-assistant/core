"""Tests for the SolarEdge Modbus config-entry setup."""

import asyncio
from datetime import timedelta
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
    ModbusUnit,
    ServerDeviceFailureError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from solaredged import InverterStatus, SolarEdge, SolarEdgeConnectionError

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.solaredge_modbus.const import (
    ATTACHMENT_SCAN_INTERVAL,
    CONF_SILENT_BLOCKS,
    DOMAIN,
    LOGGER,
    READ_TIMEOUT,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
    SLEEP_OUTAGE_GRACE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    BATTERY_RATED_ENERGY,
    BATTERY_SERIAL_BASE,
    BATTERY_SERIAL_NUMBERS,
    METER_SERIAL_NUMBER,
    SERIAL_NUMBER,
    STORAGE_CAPACITY_BASE,
    add_storage_capacity,
    async_seed_unit,
    tcp_data,
)

POWER_ENTITY = "sensor.solaredge_se10000h_power"

# An address inside the inverter's read, to make that read fail.
INVERTER_REGISTER = 40069

# The inverter's operating state.
INVERTER_STATUS_REGISTER = 40107

# Failed readings polls a reset may take without an error, counted from the
# first one's start. The next one starts right at the end of the window.
POLLS_IN_GRACE = int(SLEEP_OUTAGE_GRACE / SCAN_INTERVAL)

# Readings polls per settings poll, which runs far less often.
POLLS_PER_SETTINGS_POLL = int(SETTINGS_SCAN_INTERVAL / SCAN_INTERVAL)

# How each coordinator logs a failed refresh.
READINGS_ERROR = "Error fetching SolarEdge SE10000H readings data"
SETTINGS_ERROR = "Error fetching SolarEdge SE10000H settings data"

# How long a connection attempt to a silent address waits, as in the report.
CONNECT_TIMEOUT = timedelta(seconds=10)

# The register the probe counts meters by.
METER_MODEL_REGISTER = 40188

# The identifier the multiple-MPPT probe reads, which sets the meter offset.
MMPPT_REGISTER = 40121

# An address inside the pooled storage and export control read.
SITE_CONTROL_REGISTER = 57348

# The first register of the power control block, which the probe asks for.
POWER_CONTROL_REGISTER = 61440

# Where the first meter's serial number lives.
METER_SERIAL_REGISTER = 40171

EXPORT_LIMITATION_ENTITY = "select.solaredge_se10000h_export_limitation"
EXTERNAL_PRODUCTION_ENTITY = "switch.solaredge_se10000h_external_production"
ACTIVE_POWER_LIMIT_ENTITY = "number.solaredge_se10000h_active_power_limit"
BACKUP_RESERVE_ENTITY = "number.solaredge_se10000h_backup_reserve"
SITE_EXPORT_LIMIT_ENTITY = "number.solaredge_se10000h_site_export_limit"
ON_GRID_ENTITY = "binary_sensor.solaredge_se10000h_on_grid"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _tick_polls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int
) -> None:
    """Let the readings poll run the given number of times."""
    for _ in range(polls):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


def _records(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return what this integration logged at the given level or above."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER.name and record.levelno >= level
    ]


def _errors_from(caplog: pytest.LogCaptureFixture, prefix: str) -> int:
    """Count the refresh errors one coordinator logged."""
    return sum(m.startswith(prefix) for m in _records(caplog, logging.ERROR))


def _is_control_read(address: int, count: int) -> bool:
    """Return whether a read belongs to the settings poll."""
    return (
        address <= SITE_CONTROL_REGISTER < address + count
        or address >= POWER_CONTROL_REGISTER
    )


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
        (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}"),
        mock_config_entry.entry_id,
    )
    assert meter is not None
    assert meter.via_device_id == inverter.id
    assert meter.name == "Meter 1"
    assert meter.model_id == "SE-MTR-3Y-400V-A"
    assert meter.serial_number == METER_SERIAL_NUMBER


async def test_meter_without_a_serial_number_is_known_by_its_slot(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Not every meter names itself, and then its place on the inverter does.

    The fallback says which slot it is rather than just the number, so it
    cannot be read as a serial number that happens to be short.
    """
    mock_modbus_unit.holding.update(dict.fromkeys(range(40171, 40187), 0))

    await _setup(hass, mock_config_entry)

    meter = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{SERIAL_NUMBER}_meter_slot_1"), mock_config_entry.entry_id
    )
    assert meter is not None
    assert meter.serial_number is None


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

    meter_identifier = (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}")
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


async def test_setup_retry_when_a_meter_is_unreadable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter that answers the probe but not the poll holds up setup.

    Which sensors a meter offers is decided from its DID, once, so an entry
    accepted without it would be missing its phase measurements until a reload.
    """
    mock_modbus_unit.fail_read(40190, ServerDeviceFailureError())

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_meter_that_did_not_answer_the_probe_is_kept(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Silence while probing is not proof that a meter is gone.

    The library takes a block that does not answer for absent, which keeps the
    rest of the device usable. Removing the device on that would throw away a
    meter's history over a single timeout.
    """
    await _setup(hass, mock_config_entry)

    meter_identifier = (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}")
    assert (
        device_registry.async_get_device_by_identifier(
            meter_identifier, mock_config_entry.entry_id
        )
        is not None
    )

    mock_modbus_unit.fail_read(40188, ModbusTimeoutError("timed out"))

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            meter_identifier, mock_config_entry.entry_id
        )
        is not None
    )


async def test_replaced_meter_is_a_new_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Another meter in the same place is another device.

    Its counters start where the old meter's did not, and reusing the device
    would hold the new readings against the old meter's totals.
    """
    await _setup(hass, mock_config_entry)

    replacement = "7E5B22D3"
    padded = replacement.ljust(32, "\0").encode()
    mock_modbus_unit.holding.update(
        {
            40171 + index: (padded[index * 2] << 8) | padded[index * 2 + 1]
            for index in range(16)
        }
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}"),
            mock_config_entry.entry_id,
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SERIAL_NUMBER}_meter_{replacement}"),
            mock_config_entry.entry_id,
        )
        is not None
    )


async def test_batteries_are_sub_devices_of_the_inverter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Each battery is hardware of its own, hanging off the inverter."""
    await _setup(hass, mock_config_entry)

    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
    )
    assert inverter is not None

    for index, serial_number in enumerate(BATTERY_SERIAL_NUMBERS, 1):
        battery = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SERIAL_NUMBER}_battery_{serial_number}"),
            mock_config_entry.entry_id,
        )
        assert battery is not None
        assert battery.via_device_id == inverter.id
        assert battery.name == f"Battery {index}"
        assert battery.model_id == "SE-BAT-48V-10KWH"
        assert battery.serial_number == serial_number


async def test_battery_that_left_the_installation_is_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A battery taken out does not linger as a device.

    The inverter refusing its block is the device saying it is gone, where
    silence would only mean it did not answer this time.
    """
    await _setup(hass, mock_config_entry)

    identifiers = [
        (DOMAIN, f"{SERIAL_NUMBER}_battery_{serial_number}")
        for serial_number in BATTERY_SERIAL_NUMBERS
    ]
    assert all(
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is not None
        for identifier in identifiers
    )

    mock_modbus_unit.fail_read(BATTERY_RATED_ENERGY, IllegalDataAddressError())

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert all(
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is None
        for identifier in identifiers
    )


async def test_battery_that_did_not_answer_the_probe_is_kept(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Silence while probing is not proof that a battery is gone."""
    await _setup(hass, mock_config_entry)

    identifier = (DOMAIN, f"{SERIAL_NUMBER}_battery_{BATTERY_SERIAL_NUMBERS[0]}")
    assert (
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is not None
    )

    mock_modbus_unit.fail_read(BATTERY_RATED_ENERGY, ModbusTimeoutError("timed out"))

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is not None
    )


async def test_silence_about_one_kind_does_not_shield_the_other(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter that is really gone goes, even when the batteries kept quiet.

    Silence about one kind of attached hardware says nothing about the other,
    and holding on to everything would leave a removed meter behind for as long
    as a battery is slow to answer.
    """
    await _setup(hass, mock_config_entry)

    meter = (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}")
    battery = (DOMAIN, f"{SERIAL_NUMBER}_battery_{BATTERY_SERIAL_NUMBERS[0]}")

    mock_modbus_unit.fail_read(BATTERY_RATED_ENERGY, ModbusTimeoutError("timed out"))
    mock_modbus_unit.fail_read(METER_MODEL_REGISTER, IllegalDataAddressError())

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            meter, mock_config_entry.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            battery, mock_config_entry.entry_id
        )
        is not None
    )


async def test_battery_without_a_serial_number_is_known_by_its_slot(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Not every battery names itself, and then its place on the inverter does."""
    mock_modbus_unit.holding.update(
        dict.fromkeys(range(BATTERY_SERIAL_BASE, BATTERY_SERIAL_BASE + 16), 0)
    )

    await _setup(hass, mock_config_entry)

    battery = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{SERIAL_NUMBER}_battery_slot_1"), mock_config_entry.entry_id
    )
    assert battery is not None
    assert battery.serial_number is None


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
        await hass.async_block_till_done(wait_background_tasks=True)

    assert missed  # the read really did fail

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("status", "errors"),
    [
        pytest.param(InverterStatus.SLEEPING, 0, id="sleeping"),
        pytest.param(InverterStatus.OFF, 1, id="off"),
        pytest.param(InverterStatus.STARTING, 1, id="starting"),
        pytest.param(InverterStatus.PRODUCING, 1, id="producing"),
        pytest.param(InverterStatus.FAULT, 1, id="fault"),
    ],
)
async def test_dead_link_is_an_error_unless_sleeping(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    status: InverterStatus,
    errors: int,
) -> None:
    """A device that answers nothing at all leaves every value stale.

    The entities go unavailable whatever the inverter was doing. Only a
    sleeping one gets away without an error: SolarEdge inverters reset while
    asleep and refuse connections for about a minute. One that just woke up
    is read awake first, so its sleep does not carry over.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = status
    await _tick_polls(hass, freezer, 1)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _errors_from(caplog, READINGS_ERROR) == errors
    assert len(_records(caplog, logging.ERROR)) == errors


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusTimeoutError("timed out"), id="silent"),
        pytest.param(ModbusConnectionError("could not connect"), id="refused"),
    ],
)
async def test_sleeping_inverter_comes_back_after_a_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    error: Exception,
) -> None:
    """A reset leaves nothing in the log, and the entities read again after it."""
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)
    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    power = state.state
    caplog.clear()

    mock_modbus_unit.fail_requests(error)
    await _tick_polls(hass, freezer, POLLS_IN_GRACE)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_modbus_unit.fail_requests(None)
    await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == power
    assert _records(caplog, logging.INFO) == []


async def test_reported_reset_leaves_nothing_in_the_log(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The reset from the report, with the time it takes, stays out of the log.

    Two connection attempts wait out their timeout, the third is refused, and
    the fourth finds the inverter back.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)
    caplog.clear()

    read_holding_registers = mock_modbus_unit.read_holding_registers
    attempts = ["silent", "silent", "refused"]

    async def reset(address: int, count: int) -> list[int]:
        """Answer the way the reported inverter did while it reset."""
        if not attempts:
            return await read_holding_registers(address, count)
        if attempts.pop(0) == "refused":
            raise ModbusConnectionError("could not connect")
        freezer.tick(CONNECT_TIMEOUT)
        raise ModbusTimeoutError("timed out")

    with patch.object(mock_modbus_unit, "read_holding_registers", reset):
        await _tick_polls(hass, freezer, 4)

    assert attempts == []  # the whole reset was played out
    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert _records(caplog, logging.INFO) == []


async def test_slow_poll_does_not_use_up_the_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A poll that read the inverter asleep counts from when it was done.

    Here the meter and batteries time out on the first attempt and the retry,
    which keeps that poll busy for minutes. A reset right after it is still a
    reset.
    """
    await _setup(hass, mock_config_entry)
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING

    read_holding_registers = mock_modbus_unit.read_holding_registers

    async def slow_attachments(address: int, count: int) -> list[int]:
        """Let every read past the inverter's wait out its timeout."""
        if address > INVERTER_REGISTER and not _is_control_read(address, count):
            freezer.tick(READ_TIMEOUT)
            raise ModbusTimeoutError("timed out")
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", slow_attachments):
        await _tick_polls(hass, freezer, 1)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR) == []


async def test_failed_poll_counts_from_its_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The timeout a failed poll waits out does not use up the window.

    The inverter was last read asleep at setup; its own read fails after that,
    so the window keeps counting from there. The poll that finds the link dead
    starts inside the window and only ends past it.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_read(INVERTER_REGISTER, ModbusTimeoutError("timed out"))
    await _tick_polls(hass, freezer, POLLS_IN_GRACE - 2)

    async def wait_out_the_timeout(address: int, count: int) -> list[int]:
        """Let the first read of the poll hang until it times out."""
        freezer.tick(READ_TIMEOUT)
        raise ModbusTimeoutError("timed out")

    with patch.object(mock_modbus_unit, "read_holding_registers", wait_out_the_timeout):
        await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR) == []


async def test_sleeping_inverter_gone_past_the_grace_is_an_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A link that stays dead longer than a reset takes is logged once.

    The first poll past the window is the one that logs. Its return is then
    the coordinator's own business, logged once as well.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, POLLS_IN_GRACE)
    assert _records(caplog, logging.ERROR) == []

    await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _errors_from(caplog, READINGS_ERROR) == 1

    mock_modbus_unit.fail_requests(None)
    await _tick_polls(hass, freezer, 1)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert len(_records(caplog, logging.ERROR)) == 1
    assert (
        sum(message.endswith("recovered") for message in _records(caplog, logging.INFO))
        == 1
    )


async def test_each_reset_gets_its_own_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A poll that answers in between ends one reset, and the next starts over."""
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, POLLS_IN_GRACE)
    mock_modbus_unit.fail_requests(None)
    await _tick_polls(hass, freezer, 1)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, POLLS_IN_GRACE)

    assert _records(caplog, logging.ERROR) == []


async def test_each_coordinator_counts_its_own_outage(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Readings failing while the settings poll answers are no reset.

    The settings poll answering does not end the readings outage, so it is
    logged once, and nothing claims it recovered.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    read_holding_registers = mock_modbus_unit.read_holding_registers

    async def refuse_the_readings(address: int, count: int) -> list[int]:
        """Answer every read outside the control blocks with an exception."""
        if not _is_control_read(address, count):
            raise ServerDeviceFailureError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", refuse_the_readings):
        await _tick_polls(hass, freezer, 2 * POLLS_PER_SETTINGS_POLL)

    state = hass.states.get(ACTIVE_POWER_LIMIT_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE  # the settings poll really answered
    assert _errors_from(caplog, READINGS_ERROR) == 1
    assert not any(
        message.endswith("recovered") for message in _records(caplog, logging.INFO)
    )


async def test_settings_failing_for_long_are_an_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A settings poll that keeps failing is no reset, even with the inverter asleep.

    The readings poll reads it asleep every few seconds meanwhile, which must
    not keep the settings outage quiet all night.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    read_holding_registers = mock_modbus_unit.read_holding_registers

    async def refuse_the_settings(address: int, count: int) -> list[int]:
        """Answer every read of the control blocks with an exception."""
        if _is_control_read(address, count):
            raise ServerDeviceFailureError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", refuse_the_settings):
        await _tick_polls(hass, freezer, 2 * POLLS_PER_SETTINGS_POLL)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE  # the readings poll really answered
    assert _errors_from(caplog, SETTINGS_ERROR) == 1


async def test_sleeping_read_after_the_outage_began_excuses_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A readings poll that answered after settings began failing proves a link.

    A settings refresh asked for right after it, here through an entity update,
    is no reset, however soon.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    read_holding_registers = mock_modbus_unit.read_holding_registers

    async def refuse_the_settings(address: int, count: int) -> list[int]:
        """Answer every read of the control blocks with an exception."""
        if _is_control_read(address, count):
            raise ServerDeviceFailureError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", refuse_the_settings):
        await _tick_polls(hass, freezer, POLLS_PER_SETTINGS_POLL + 1)
        assert _records(caplog, logging.ERROR) == []
        await hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: ACTIVE_POWER_LIMIT_ENTITY},
            blocking=True,
        )

    assert _errors_from(caplog, SETTINGS_ERROR) == 1


@pytest.mark.parametrize(
    ("answered_polls", "errors"),
    [
        pytest.param(POLLS_PER_SETTINGS_POLL - 1, 0, id="reset"),
        pytest.param(0, 1, id="long_outage"),
    ],
)
async def test_settings_poll_counts_from_the_last_sleeping_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    answered_polls: int,
    errors: int,
) -> None:
    """The settings poll takes the readings poll's word for the inverter's sleep.

    It runs far less often, so a reset that the readings saw begin finds it
    within the window, and a link that died long before it ran does not.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    await _tick_polls(hass, freezer, answered_polls)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, POLLS_PER_SETTINGS_POLL - answered_polls)

    state = hass.states.get(ACTIVE_POWER_LIMIT_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _errors_from(caplog, SETTINGS_ERROR) == errors


async def test_sleep_is_only_taken_from_a_fresh_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A status kept from an earlier poll does not renew the inverter's sleep.

    While the inverter's own read fails, its status is whatever an earlier
    poll left, and the inverter may well be awake by now.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_read(INVERTER_REGISTER, ModbusTimeoutError("timed out"))
    await _tick_polls(hass, freezer, POLLS_IN_GRACE - 1)

    # This poll starts right at the end of the window from the setup's read.
    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, 1)

    assert _errors_from(caplog, READINGS_ERROR) == 1


async def test_no_reset_after_another_inverter_answered(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Once a poll failed, a dead link right after it is no reset either.

    Here another inverter answered on the address first. Taking the dead link
    after it for a reset would claim the entry recovered.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _setup(hass, mock_config_entry)

    await async_seed_unit(
        hass, mock_modbus_unit, serial_registers=[20308, 18501, 21041, 12851]
    )
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    await _tick_polls(hass, freezer, 1)

    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))
    await _tick_polls(hass, freezer, 1)

    assert not any(
        message.endswith("recovered") for message in _records(caplog, logging.INFO)
    )


async def test_retry_dying_still_counts_the_first_answer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A poll whose retry died still found the inverter asleep.

    The reset can start between the first attempt and its retry, and the next
    failed poll is then part of that same reset. The sub-system the first
    attempt missed is still logged as a warning.
    """
    await _setup(hass, mock_config_entry)
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING

    read_holding_registers = mock_modbus_unit.read_holding_registers
    dead = False

    async def die_after_the_meter(address: int, count: int) -> list[int]:
        """Miss the meter's read, then let nothing answer at all."""
        nonlocal dead
        if dead or address <= METER_MODEL_REGISTER < address + count:
            dead = True
            raise ModbusTimeoutError("link died")
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", die_after_the_meter):
        await _tick_polls(hass, freezer, 2)

    assert dead  # the link really did die
    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR) == []
    assert any("meters[0]" in m for m in _records(caplog, logging.WARNING))


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
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.readings.last_update_success is False

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_silent_control_block_leaves_the_others_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Storage and export controls share one read; power control has its own."""
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_read(SITE_CONTROL_REGISTER, ServerDeviceFailureError())
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("number.solaredge_se10000h_backup_reserve")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("number.solaredge_se10000h_active_power_limit")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_settings_failure_does_not_block_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Readings carry the entry even when the control blocks stay silent.

    The failure is reported even though the inverter was just read asleep:
    the first refresh has nothing yet to mark as failed.
    """
    mock_modbus_unit.holding[INVERTER_STATUS_REGISTER] = InverterStatus.SLEEPING
    with patch(
        "homeassistant.components.solaredge_modbus.SolarEdge.async_update_settings",
        side_effect=SolarEdgeConnectionError("timed out"),
    ):
        await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(POWER_ENTITY) is not None

    state = hass.states.get("number.solaredge_se10000h_backup_reserve")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert _errors_from(caplog, SETTINGS_ERROR) == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_concurrent_control_writes_keep_both_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Two writes to the same control register do not clobber each other.

    The export mode and its flags live in one register, which the library
    changes by taking its cached value, flipping bits and writing it back.
    Select and switch have separate parallel-update semaphores, so without
    serialization the second write undoes the first.
    """
    await _setup(hass, mock_config_entry)

    write_register = mock_modbus_unit.write_register

    async def write_register_slowly(address: int, value: int) -> None:
        """Write with a suspension point, which a real link has and a mock lacks."""
        await asyncio.sleep(0)
        await write_register(address, value)

    mock_modbus_unit.write_register = write_register_slowly

    await asyncio.gather(
        hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: EXPORT_LIMITATION_ENTITY,
                ATTR_OPTION: "production_control",
            },
            blocking=True,
        ),
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: EXTERNAL_PRODUCTION_ENTITY},
            blocking=True,
        ),
    )

    state = hass.states.get(EXPORT_LIMITATION_ENTITY)
    assert state is not None
    assert state.state == "production_control"

    state = hass.states.get(EXTERNAL_PRODUCTION_ENTITY)
    assert state is not None
    assert state.state == STATE_ON


async def _tick_attachment_check(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> int:
    """Let the check for changed hardware run, and report what it cost.

    Setting up probes the device, so a check that reloads the entry probes
    twice: once to look, once to build the entry again.
    """
    probes = 0
    probe = SolarEdge.async_probe

    async def counting_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        nonlocal probes
        probes += 1
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", counting_probe):
        freezer.tick(ATTACHMENT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    return probes


async def test_meter_added_later_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter wired to a running installation appears without being asked.

    What is attached is read while the entry is set up, so the entry loads
    again once a probe finds something that was not there before.
    """
    mock_modbus_unit.fail_read(METER_MODEL_REGISTER, IllegalDataAddressError())
    await _setup(hass, mock_config_entry)

    meter = (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}")
    assert (
        device_registry.async_get_device_by_identifier(
            meter, mock_config_entry.entry_id
        )
        is None
    )

    # The meter is wired in and answers from now on.
    mock_modbus_unit.fail_read(METER_MODEL_REGISTER, None)

    await _tick_attachment_check(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            meter, mock_config_entry.entry_id
        )
        is not None
    )


async def test_battery_removed_later_is_dropped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A battery taken out of a running installation stops being a device."""
    await _setup(hass, mock_config_entry)

    battery = (DOMAIN, f"{SERIAL_NUMBER}_battery_{BATTERY_SERIAL_NUMBERS[0]}")
    assert (
        device_registry.async_get_device_by_identifier(
            battery, mock_config_entry.entry_id
        )
        is not None
    )

    mock_modbus_unit.fail_read(BATTERY_RATED_ENERGY, IllegalDataAddressError())

    await _tick_attachment_check(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            battery, mock_config_entry.entry_id
        )
        is None
    )


async def test_replaced_meter_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Another meter in the same place is another device, while running too.

    Swapping one meter for another leaves the count alone, so what gives it
    away is the serial number the polls have been reading all along.
    """
    await _setup(hass, mock_config_entry)

    replacement = "7E9C55A6"
    padded = replacement.ljust(32, "\0").encode()
    mock_modbus_unit.holding.update(
        {
            METER_SERIAL_REGISTER + index: (padded[index * 2] << 8)
            | padded[index * 2 + 1]
            for index in range(16)
        }
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The swap is seen without probing, so the only probe here is the reload's.
    assert await _tick_attachment_check(hass, freezer) == 1

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}"),
            mock_config_entry.entry_id,
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SERIAL_NUMBER}_meter_{replacement}"),
            mock_config_entry.entry_id,
        )
        is not None
    )


@pytest.mark.parametrize(
    ("register", "entity_id"),
    [
        pytest.param(40113, ON_GRID_ENTITY, id="grid status"),
        pytest.param(57348, BACKUP_RESERVE_ENTITY, id="storage control"),
        pytest.param(57344, SITE_EXPORT_LIMIT_ENTITY, id="export control"),
        pytest.param(61440, ACTIVE_POWER_LIMIT_ENTITY, id="power control"),
    ],
)
async def test_block_that_answers_later_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    register: int,
    entity_id: str,
) -> None:
    """A block that answers only after setup still gets its entities."""
    mock_modbus_unit.fail_read(register, ModbusTimeoutError("timed out"))
    await _setup(hass, mock_config_entry)

    assert hass.states.get(entity_id) is None

    mock_modbus_unit.fail_read(register, None)

    await _tick_attachment_check(hass, freezer)

    assert hass.states.get(entity_id) is not None


@pytest.mark.parametrize(
    ("register", "entity_id"),
    [
        pytest.param(40113, ON_GRID_ENTITY, id="grid status"),
        pytest.param(57348, BACKUP_RESERVE_ENTITY, id="storage control"),
        pytest.param(57344, SITE_EXPORT_LIMIT_ENTITY, id="export control"),
        pytest.param(61440, ACTIVE_POWER_LIMIT_ENTITY, id="power control"),
    ],
)
async def test_block_going_quiet_does_not_trigger_a_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    register: int,
    entity_id: str,
) -> None:
    """A block going quiet is not the inverter saying it does not have one."""
    await _setup(hass, mock_config_entry)

    mock_modbus_unit.fail_read(register, ModbusTimeoutError("timed out"))

    assert await _tick_attachment_check(hass, freezer) == 1

    assert hass.states.get(entity_id) is not None


async def test_silent_attachment_does_not_trigger_a_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A meter that did not answer the probe is not a meter that was removed.

    Silence is taken for absence while probing, so reloading on it would drop a
    device, and its history, over a single timeout.
    """
    await _setup(hass, mock_config_entry)

    meter = (DOMAIN, f"{SERIAL_NUMBER}_meter_{METER_SERIAL_NUMBER}")
    mock_modbus_unit.fail_read(METER_MODEL_REGISTER, ModbusTimeoutError("timed out"))

    assert await _tick_attachment_check(hass, freezer) == 1

    assert (
        device_registry.async_get_device_by_identifier(
            meter, mock_config_entry.entry_id
        )
        is not None
    )


async def test_unchanged_attachments_leave_the_entry_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Nothing changed means nothing happens, however often it is checked."""
    await _setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.readings

    assert await _tick_attachment_check(hass, freezer) == 1

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # A reload would have built new coordinators.
    assert mock_config_entry.runtime_data.readings is coordinator


async def test_a_dead_probe_leaves_the_entry_where_it_is(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An inverter that stops answering says nothing about what is wired to it.

    The coordinators already report an inverter gone quiet; reloading on top of
    that would only take the entry down with it.
    """
    await _setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.readings
    mock_modbus_unit.fail_requests(ModbusTimeoutError("link died"))

    assert await _tick_attachment_check(hass, freezer) == 1

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.readings is coordinator


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
        await hass.async_block_till_done(wait_background_tasks=True)

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


async def test_a_block_that_stays_silent_stops_being_asked(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A block silent at setup is looked for once more, then left alone.

    Asking costs a full timeout each time, and the link is shared, so that is
    time every other inverter on it spends queued behind the question.
    """
    mock_modbus_unit.fail_read(POWER_CONTROL_REGISTER, ModbusTimeoutError("timed out"))
    await _setup(hass, mock_config_entry)

    asked: list[frozenset[str]] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        asked.append(assume_absent)
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", recording_probe):
        for _ in range(2):
            freezer.tick(ATTACHMENT_SCAN_INTERVAL)
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert asked[0] == frozenset(), "the first check still looks for it"
    assert "power_control" in asked[1], "a block still silent is not asked again"


async def test_a_block_that_blips_once_keeps_being_asked(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A block that answered at setup is not settled by one timeout later.

    Settling it would hide the block going away for good, since a block taken
    for absent is reported back as though it had been silent again.
    """
    await _setup(hass, mock_config_entry)

    asked: list[frozenset[str]] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        asked.append(assume_absent)
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", recording_probe):
        mock_modbus_unit.fail_read(
            POWER_CONTROL_REGISTER, ModbusTimeoutError("timed out")
        )
        freezer.tick(ATTACHMENT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_modbus_unit.fail_read(POWER_CONTROL_REGISTER, None)
        freezer.tick(ATTACHMENT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "power_control" not in asked[1], "a blip settled a block that answered"


@pytest.mark.parametrize(
    ("register", "subsystem"),
    [
        pytest.param(BATTERY_RATED_ENERGY, "batteries", id="batteries"),
        pytest.param(METER_MODEL_REGISTER, "meters", id="meters"),
        pytest.param(MMPPT_REGISTER, "mmppt", id="mmppt"),
    ],
)
async def test_a_block_discovery_depends_on_keeps_being_asked(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    register: int,
    subsystem: str,
) -> None:
    """A block that finding hardware depends on is asked however quiet it stays.

    Meters and batteries each bring a device. The multiple-MPPT block decides
    the offset the meters are looked for at, so taking it for absent would look
    for them at the wrong addresses for good.
    """
    mock_modbus_unit.fail_read(register, ModbusTimeoutError("timed out"))
    await _setup(hass, mock_config_entry)

    asked: list[frozenset[str]] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        asked.append(assume_absent)
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", recording_probe):
        for _ in range(2):
            freezer.tick(ATTACHMENT_SCAN_INTERVAL)
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert subsystem not in asked[1], "a block discovery depends on was settled"


async def test_a_settled_block_is_not_waited_for_on_the_next_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A block settled as silent is taken for absent when the entry loads again.

    Each one would otherwise cost a full timeout every time the entry is set
    up, which on a slow link is most of the time that takes.
    """
    mock_modbus_unit.fail_read(POWER_CONTROL_REGISTER, ModbusTimeoutError("timed out"))
    await _setup(hass, mock_config_entry)
    await _tick_attachment_check(hass, freezer)

    assert mock_config_entry.data[CONF_SILENT_BLOCKS] == ["power_control"]

    asked: list[frozenset[str]] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        asked.append(assume_absent)
        return await probe(unit, assume_absent=assume_absent)

    caplog.clear()
    with patch.object(SolarEdge, "async_probe", recording_probe):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert asked == [frozenset({"power_control"})]
    assert "power_control" not in caplog.text, "a known silence is not news"


async def test_a_settled_block_that_answers_again_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The first check after setup still asks a settled block for real.

    The entry reloads to add what it found, so the block must be forgotten as
    silent first, or that setup would take it for absent all over again.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id=SERIAL_NUMBER,
        data={**tcp_data(), CONF_SILENT_BLOCKS: ["power_control"]},
    )
    await _setup(hass, entry)

    assert hass.states.get(ACTIVE_POWER_LIMIT_ENTITY) is None

    await _tick_attachment_check(hass, freezer)

    assert hass.states.get(ACTIVE_POWER_LIMIT_ENTITY) is not None
    assert entry.data[CONF_SILENT_BLOCKS] == []


@pytest.mark.parametrize("subsystem", ["batteries", "meters", "mmppt"])
async def test_a_stored_discovery_block_is_still_asked_at_setup(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    subsystem: str,
) -> None:
    """A block that finding hardware depends on is asked whatever was stored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id=SERIAL_NUMBER,
        data={**tcp_data(), CONF_SILENT_BLOCKS: [subsystem, "power_control"]},
    )
    asked: list[frozenset[str]] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        asked.append(assume_absent)
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", recording_probe):
        await _setup(hass, entry)

    assert asked == [frozenset({"power_control"})]


async def test_only_a_block_a_check_reloads_for_is_kept(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A silent block is only skipped at setup if the check can bring it back.

    The check reloads when a control block starts answering. A silent model
    chain, which is where storage capacity is found, does not get that reload,
    so taking it for absent at setup would hide it until something else did.
    """
    add_storage_capacity(mock_modbus_unit, state_of_charge=5960)
    mock_modbus_unit.fail_read(POWER_CONTROL_REGISTER, ModbusTimeoutError("timed out"))
    mock_modbus_unit.fail_read(STORAGE_CAPACITY_BASE, ModbusTimeoutError("timed out"))
    await _setup(hass, mock_config_entry)
    await _tick_attachment_check(hass, freezer)

    assert mock_config_entry.data[CONF_SILENT_BLOCKS] == ["power_control"]


async def test_reads_wait_longer_than_the_probe(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Polls get a longer timeout, the probe keeps the link's default.

    Over Wi-Fi some answers come late, and one late answer fails a whole poll.
    The probe waits out a full timeout for every block the inverter never
    answers, so raising it there would only make setting up slower.
    """
    during_probe: list[float | None] = []
    probe = SolarEdge.async_probe

    async def recording_probe(
        unit: ModbusUnit, *, assume_absent: frozenset[str] = frozenset()
    ) -> SolarEdge:
        during_probe.append(mock_modbus_unit.required_timeout)
        return await probe(unit, assume_absent=assume_absent)

    with patch.object(SolarEdge, "async_probe", recording_probe):
        await _setup(hass, mock_config_entry)

    assert during_probe == [None]
    assert mock_modbus_unit.required_timeout == READ_TIMEOUT
