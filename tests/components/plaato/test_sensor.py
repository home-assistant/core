"""Tests for the plaato sensors."""

from pyplaato.models.device import PlaatoDeviceType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform."""
    return Platform.SENSOR


@pytest.mark.parametrize(
    "device_type", [PlaatoDeviceType.Airlock, PlaatoDeviceType.Keg]
)
@pytest.mark.freeze_time("2024-05-24 12:00:00", tz_offset=0)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)
