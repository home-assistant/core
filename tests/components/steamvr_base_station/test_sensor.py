"""Test the SteamVR Base Station sensors."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import make_service_info, payload

POWER_STATE = "sensor.lhb_747a9bc5_power_state"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(0x0B, "on", id="on"),
        pytest.param(0x08, "booting", id="booting"),
        pytest.param(0x02, "standby", id="standby"),
        pytest.param(0x00, "sleep", id="sleep"),
        pytest.param(0x77, STATE_UNKNOWN, id="unknown_code"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_state_follows_advertisements(
    hass: HomeAssistant, code: int, expected: str
) -> None:
    """Test the power state sensor reflects the advertised power state."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(payload(power=code)))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_STATE).state == expected
