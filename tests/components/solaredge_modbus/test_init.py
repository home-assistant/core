"""Tests for the SolarEdge Modbus config-entry setup."""

import asyncio
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusTimeoutError,
    ModbusUnit,
    ServerDeviceFailureError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from solaredged import SolarEdge, SolarEdgeConnectionError

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.solaredge_modbus.const import (
    ATTACHMENT_SCAN_INTERVAL,
    DOMAIN,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
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

from .conftest import (
    BATTERY_RATED_ENERGY,
    BATTERY_SERIAL_BASE,
    BATTERY_SERIAL_NUMBERS,
    METER_SERIAL_NUMBER,
    SERIAL_NUMBER,
    async_seed_unit,
    tcp_data,
)

from tests.common import MockConfigEntry, async_fire_time_changed

POWER_ENTITY = "sensor.solaredge_se10000h_power"

# An address inside the inverter's read, to make that read fail.
INVERTER_REGISTER = 40069

# The register the probe counts meters by.
METER_MODEL_REGISTER = 40188

# An address inside the pooled storage and export control read.
SITE_CONTROL_REGISTER = 57348

# Where the first meter's serial number lives.
METER_SERIAL_REGISTER = 40171

EXPORT_LIMITATION_ENTITY = "select.solaredge_se10000h_export_limitation"
EXTERNAL_PRODUCTION_ENTITY = "switch.solaredge_se10000h_external_production"


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
    await hass.async_block_till_done()

    state = hass.states.get("number.solaredge_se10000h_backup_reserve")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("number.solaredge_se10000h_active_power_limit")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_settings_failure_does_not_block_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Readings carry the entry even when the control blocks stay silent."""
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

    async def counting_probe(unit: ModbusUnit) -> SolarEdge:
        nonlocal probes
        probes += 1
        return await probe(unit)

    with patch.object(SolarEdge, "async_probe", counting_probe):
        freezer.tick(ATTACHMENT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

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
