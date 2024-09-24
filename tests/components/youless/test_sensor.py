"""Test the sensor classes for youless."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_component

from tests.common import snapshot_platform


async def test_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the sensor classes for youless."""
    with patch("homeassistant.components.youless.PLATFORMS", [Platform.SENSOR]):
        entry = await init_component(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
