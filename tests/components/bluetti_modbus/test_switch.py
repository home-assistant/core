"""Tests for the BLUETTI Modbus switches."""

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
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SERIAL_ADDRESS

AC_OUTPUT_ENTITY = "switch.balco_260_ac_output"
AC_OUTPUT_ADDRESS = 57001


@pytest.mark.usefixtures("mock_modbus_unit")
@patch("homeassistant.components.bluetti_modbus.PLATFORMS", [Platform.SWITCH])
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All switch entities and their states match the snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "written", "state"),
    [
        pytest.param(SERVICE_TURN_OFF, 0, STATE_OFF, id="off"),
        pytest.param(SERVICE_TURN_ON, 1, STATE_ON, id="on"),
    ],
)
async def test_switch_writes_the_register(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    service: str,
    written: int,
    state: str,
) -> None:
    """Switching writes the register, and the state follows at once."""
    mock_modbus_unit.holding[AC_OUTPUT_ADDRESS] = 1 - written
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: AC_OUTPUT_ENTITY}, blocking=True
    )

    assert mock_modbus_unit.holding[AC_OUTPUT_ADDRESS] == written
    entity = hass.states.get(AC_OUTPUT_ENTITY)
    assert entity is not None
    assert entity.state == state

    # The next settings poll reads back what was written.
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(AC_OUTPUT_ENTITY)
    assert entity is not None
    assert entity.state == state


async def test_switch_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write the device does not take raises an error and changes nothing."""
    await setup_integration(hass, mock_config_entry)
    mock_modbus_unit.fail_write(AC_OUTPUT_ADDRESS, ModbusTimeoutError("timed out"))

    with pytest.raises(HomeAssistantError, match="could not be written"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: AC_OUTPUT_ENTITY},
            blocking=True,
        )

    entity = hass.states.get(AC_OUTPUT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_ON


async def test_switch_unavailable_for_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A different device at the address makes the switches unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(AC_OUTPUT_ENTITY)
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
        event.address < AC_OUTPUT_ADDRESS for event in mock_modbus_unit.read_events
    )

    mock_modbus_unit.holding[AC_OUTPUT_ADDRESS] = 0
    freezer.tick(SETTINGS_SCAN_INTERVAL - SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(AC_OUTPUT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_OFF


async def test_settings_poll_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Settings that can't be read leave the switches unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.fail_read(AC_OUTPUT_ADDRESS, ModbusTimeoutError("timed out"))
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(AC_OUTPUT_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE
