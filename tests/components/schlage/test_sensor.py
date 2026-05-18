"""Test schlage sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockSchlageConfigEntry

from tests.common import SnapshotAssertion, snapshot_platform


async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor attributes."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.SENSOR]):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
