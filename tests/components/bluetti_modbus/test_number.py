"""Tests for the BLUETTI Modbus numbers."""

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
