"""Tests for the E3/DC binary_sensor platform."""

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

from homeassistant.components.e3dc.const import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import seed

# The binary sensors for the bits of the EMS status register, lowest bit first
EMS_STATUS_ENTITY_IDS = [
    "binary_sensor.e3_dc_s10_x_charging_locked",
    "binary_sensor.e3_dc_s10_x_discharging_locked",
    "binary_sensor.e3_dc_s10_x_emergency_power_ready",
    "binary_sensor.e3_dc_s10_x_charging_limited_by_forecast",
    "binary_sensor.e3_dc_s10_x_feed_in_limited",
    "binary_sensor.e3_dc_s10_x_charging_lockout_period",
    "binary_sensor.e3_dc_s10_x_discharging_lockout_period",
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    "bit",
    [
        pytest.param(bit, id=entity_id.removeprefix("binary_sensor.e3_dc_s10_x_"))
        for bit, entity_id in enumerate(EMS_STATUS_ENTITY_IDS)
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_ems_status_bit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_unit: MockModbusUnit,
    bit: int,
) -> None:
    """Test each EMS status bit turns on its own binary sensor only."""
    seed(mock_unit, {40085: 1 << bit})  # EMS status
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    states = [hass.states.get(entity_id).state for entity_id in EMS_STATUS_ENTITY_IDS]
    expected = [STATE_OFF] * len(EMS_STATUS_ENTITY_IDS)
    expected[bit] = STATE_ON
    assert states == expected
