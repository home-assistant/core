"""Tests for the Intesis Modbus binary sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ALARM = "binary_sensor.inmbsmhi001r000_air_conditioner_alarm"
WINDOW = "binary_sensor.inmbsmhi001r000_air_conditioner_window"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_all_binary_sensors_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Every binary sensor matches its snapshot."""
    with patch(
        "homeassistant.components.intesis_modbus.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_alarm_and_window_follow_the_gateway(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The alarm and the window state follow registers 10 and 31."""
    assert hass.states.get(ALARM).state == STATE_OFF
    assert hass.states.get(WINDOW).state == STATE_OFF
    unit = mock_connection.for_unit(1)
    unit.holding[10] = 1
    unit.holding[31] = 1
    await _poll(hass, freezer)
    assert hass.states.get(ALARM).state == STATE_ON
    assert hass.states.get(WINDOW).state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_failed_block_only_takes_its_own_binary_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """A binary sensor read from a block that stops answering goes unavailable alone."""
    mock_connection.for_unit(1).fail_read(31, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert hass.states.get(WINDOW).state == STATE_UNAVAILABLE
    assert hass.states.get(ALARM).state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_unreachable_air_conditioner_takes_its_binary_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The binary sensors go unavailable with the air conditioner and come back."""
    unit = mock_connection.for_unit(1)
    unit.holding[11] = 65535
    await _poll(hass, freezer)
    assert hass.states.get(ALARM).state == STATE_UNAVAILABLE
    assert hass.states.get(WINDOW).state == STATE_UNAVAILABLE
    unit.holding[11] = 0
    await _poll(hass, freezer)
    assert hass.states.get(ALARM).state == STATE_OFF
    assert hass.states.get(WINDOW).state == STATE_OFF
