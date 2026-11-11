"""Tests for the Zehnder ComfoConnect PRO sensor platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comfoconnect_modbus.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import INPUT, seed, setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test that all sensors get created with their states."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_co2_zone_added_when_it_reports(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test that a CO₂ zone sensor gets created when it first reports."""
    assert hass.states.get("sensor.comfoair_co2_zone_2") is None

    seed(mock_unit, input_registers={0x0013: 455})  # CO₂ zone 2
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.comfoair_co2_zone_2").state == "455"


@pytest.mark.usefixtures("mock_get_unit")
async def test_room_sensors_added_when_they_report(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    platforms: list[Platform],
) -> None:
    """Test that room sensors get created when they first report."""
    # Room temperature and room humidity
    seed(mock_unit, input_registers={0x0008: 0, 0x000D: 0})
    await setup_integration(hass, mock_config_entry, platforms)

    assert hass.states.get("sensor.comfoair_room_temperature") is None
    assert hass.states.get("sensor.comfoair_room_humidity") is None
    assert hass.states.get("sensor.comfoair_extract_air_temperature").state == "21.8"

    seed(mock_unit, input_registers={0x0008: 215, 0x000D: 48})
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.comfoair_room_temperature").state == "21.5"
    assert hass.states.get("sensor.comfoair_room_humidity").state == "48"


@pytest.mark.parametrize(
    ("code", "state"),
    [
        pytest.param(0, "none", id="empty"),
        pytest.param(36, STATE_UNKNOWN, id="unlisted"),
        pytest.param(101, "comfonet_err", id="listed"),
    ],
)
async def test_active_error_states(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    code: int,
    state: str,
) -> None:
    """Test that an alarm slot shows none, the alarm, or unknown."""
    seed(mock_unit, input_registers={**INPUT, 0x0002: code})  # Alarm slot 1
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.comfoair_active_error_1").state == state


async def test_co2_zone_reading_zero_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test that a CO₂ zone reading 0 shows unknown."""
    seed(mock_unit, input_registers={0x0012: 0})  # CO₂ zone 1
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.comfoair_co2_zone_1").state == STATE_UNKNOWN
