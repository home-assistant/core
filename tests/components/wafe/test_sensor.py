"""Tests for the WAFE sensor platform."""

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wafe.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

STATE_ENTITY = "sensor.wafe_w201_state"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(2, "standby", id="standby"),
        pytest.param(3, "holiday", id="holiday"),
        pytest.param(4, "manual", id="manual"),
        pytest.param(0, STATE_UNKNOWN, id="none"),
        pytest.param(9, STATE_UNKNOWN, id="undocumented"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_state(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    raw: int,
    expected: str,
) -> None:
    """Test the unit state maps to the enum options."""
    mock_unit.input[1002] = raw
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATE_ENTITY).state == expected
