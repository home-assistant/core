"""Test the SteamVR Base Station fault binary sensor."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import make_service_info, payload

FAULT = "binary_sensor.lhb_747a9bc5_problem"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the binary sensor platform."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensor_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("fault", "expected"),
    [pytest.param(0, STATE_OFF, id="ok"), pytest.param(1, STATE_ON, id="fault")],
)
@pytest.mark.usefixtures("init_integration")
async def test_fault_follows_advertisements(
    hass: HomeAssistant, fault: int, expected: str
) -> None:
    """Test the fault sensor reflects the advertised fault flag."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(payload(fault=fault)))
    await hass.async_block_till_done()
    assert hass.states.get(FAULT).state == expected
