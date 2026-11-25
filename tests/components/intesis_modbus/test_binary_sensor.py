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


@pytest.mark.parametrize(
    ("address", "entity_id", "other"),
    [
        pytest.param(10, ALARM, WINDOW, id="alarm"),
        pytest.param(31, WINDOW, ALARM, id="window"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_follows_its_own_register(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    address: int,
    entity_id: str,
    other: str,
) -> None:
    """The alarm follows register 10 and the window register 31, each alone."""
    assert hass.states.get(entity_id).state == STATE_OFF
    mock_connection.for_unit(1).holding[address] = 1
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(other).state == STATE_OFF


@pytest.mark.parametrize(
    ("address", "entity_id", "other"),
    [
        pytest.param(0, ALARM, WINDOW, id="control"),
        pytest.param(31, WINDOW, ALARM, id="window"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_failed_block_only_takes_its_own_binary_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    address: int,
    entity_id: str,
    other: str,
) -> None:
    """A binary sensor goes unavailable alone with its block, and comes back."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(address, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(other).state == STATE_OFF
    unit.fail_read(address, None)
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_OFF


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
