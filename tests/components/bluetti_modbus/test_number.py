"""Tests for the BLUETTI Modbus numbers."""

import asyncio
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import (
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SERIAL, SERIAL_ADDRESS

DISCHARGE_LIMIT_ENTITY = "number.balco_260_discharge_limit"
DISCHARGE_LIMIT_ADDRESS = 57016
CHARGE_LIMIT_ENTITY = "number.balco_260_charge_limit"
CHARGE_LIMIT_ADDRESS = 57017


@pytest.mark.usefixtures("mock_modbus_unit")
@patch("homeassistant.components.bluetti_modbus.PLATFORMS", [Platform.NUMBER])
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All number entities and their states match the snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_writes_the_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Setting a value writes the register, and the state follows at once."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
        blocking=True,
    )

    assert mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] == 20
    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "20"


async def _let_tasks_run() -> None:
    """Let the pending tasks run as far as they can without blocking."""
    for _ in range(20):
        await asyncio.sleep(0)


async def test_queued_write_is_dropped_for_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write waiting its turn is not sent once another device answers."""
    await setup_integration(hass, mock_config_entry)
    write_register = mock_modbus_unit.write_register
    release = asyncio.Event()
    written: list[int] = []

    async def held_write(address: int, value: int) -> None:
        written.append(address)
        await release.wait()
        await write_register(address, value)

    with patch.object(mock_modbus_unit, "write_register", held_write):
        first = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY, ATTR_VALUE: 95},
                blocking=True,
            )
        )
        # Waits for the first one: the platform takes one action at a time.
        second = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
                blocking=True,
            )
        )
        await _let_tasks_run()
        assert written == [CHARGE_LIMIT_ADDRESS]

        mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await _let_tasks_run()

        release.set()
        await first
        with pytest.raises(HomeAssistantError, match="setting was not written"):
            await second

    assert written == [CHARGE_LIMIT_ADDRESS]


async def test_write_waits_for_a_poll_that_finds_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write that waits for a running poll is dropped if the poll fails."""
    await setup_integration(hass, mock_config_entry)
    read_holding_registers = mock_modbus_unit.read_holding_registers
    release = asyncio.Event()
    written: list[int] = []

    async def held_read(address: int, count: int) -> list[int]:
        await release.wait()
        return await read_holding_registers(address, count)

    async def recorded_write(address: int, value: int) -> None:
        written.append(address)

    mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
    with (
        patch.object(mock_modbus_unit, "read_holding_registers", held_read),
        patch.object(mock_modbus_unit, "write_register", recorded_write),
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await _let_tasks_run()
        # The poll holds the lock; the write passes the entity's own check.
        write = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY, ATTR_VALUE: 95},
                blocking=True,
            )
        )
        await _let_tasks_run()
        release.set()
        with pytest.raises(HomeAssistantError, match="setting was not written"):
            await write

    assert written == []


async def test_running_settings_poll_does_not_undo_a_write(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A settings read already under way cannot show the value from before a write."""
    await setup_integration(hass, mock_config_entry)
    read_holding_registers = mock_modbus_unit.read_holding_registers
    release = asyncio.Event()

    async def held_settings_read(address: int, count: int) -> list[int]:
        # The reply is read off the device before the write, and only
        # handed back after it.
        registers = await read_holding_registers(address, count)
        if address == DISCHARGE_LIMIT_ADDRESS:
            await release.wait()
        return registers

    with patch.object(mock_modbus_unit, "read_holding_registers", held_settings_read):
        freezer.tick(SETTINGS_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await _let_tasks_run()
        write = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
                blocking=True,
            )
        )
        await _let_tasks_run()
        release.set()
        await write
        await hass.async_block_till_done()

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "20"
    assert mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] == 20


async def test_settings_read_queued_behind_a_write_is_skipped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A settings read that waited for a write does not show the old value."""
    await setup_integration(hass, mock_config_entry)
    old_value = mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS]
    read_holding_registers = mock_modbus_unit.read_holding_registers
    write_register = mock_modbus_unit.write_register
    release = asyncio.Event()

    async def held_write(address: int, value: int) -> None:
        await release.wait()
        await write_register(address, value)

    async def lagging_read(address: int, count: int) -> list[int]:
        # Right after a write, the device still serves the old value.
        registers = await read_holding_registers(address, count)
        if address == DISCHARGE_LIMIT_ADDRESS:
            registers[0] = old_value
        return registers

    with (
        patch.object(mock_modbus_unit, "write_register", held_write),
        patch.object(mock_modbus_unit, "read_holding_registers", lagging_read),
    ):
        write = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
                blocking=True,
            )
        )
        await _let_tasks_run()
        # The settings poll comes due while the write holds the lock.
        freezer.tick(SETTINGS_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await _let_tasks_run()
        release.set()
        await write
        await hass.async_block_till_done()

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "20"


async def test_settings_from_another_device_are_not_shown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Settings read while another device answers are dropped, not kept."""
    await setup_integration(hass, mock_config_entry)

    # Another device, with its own discharge limit, answers for one settings poll.
    mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
    mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] = 50
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # This entry's device is back before the next settings poll.
    mock_modbus_unit.holding[SERIAL_ADDRESS] = int(SERIAL)
    mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] = 15
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE

    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "15"


async def test_number_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write the device does not take raises an error and changes nothing."""
    await setup_integration(hass, mock_config_entry)
    mock_modbus_unit.fail_write(
        DISCHARGE_LIMIT_ADDRESS, ModbusTimeoutError("timed out")
    )

    with pytest.raises(HomeAssistantError, match="could not be written"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
            blocking=True,
        )

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "15"


async def test_number_unavailable_for_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A different device at the address makes the numbers unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE


async def test_settings_are_read_on_their_own_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The settings are not read with every reading poll."""
    await setup_integration(hass, mock_config_entry)
    mock_modbus_unit.read_events.clear()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_modbus_unit.read_events
    assert all(
        event.address < DISCHARGE_LIMIT_ADDRESS
        for event in mock_modbus_unit.read_events
    )

    mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] = 33
    freezer.tick(SETTINGS_SCAN_INTERVAL - SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "33"


async def test_settings_poll_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Settings that can't be read leave the numbers unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.fail_read(DISCHARGE_LIMIT_ADDRESS, ModbusTimeoutError("timed out"))
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE
