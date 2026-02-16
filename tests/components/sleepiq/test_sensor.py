"""The tests for SleepIQ sensor platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform

from tests.common import snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_asyncsleepiq,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the SleepIQ sleepnumber for a bed with two sides."""
    entry = await setup_platform(hass, SENSOR_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
