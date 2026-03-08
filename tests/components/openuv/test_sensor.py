"""Test OpenUV sensors."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyopenuv: None,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensors created by the integration."""
    with patch("homeassistant.components.openuv.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
