"""Test for the switch platform entity of the foscam component."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foscam.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID)
    entry.add_to_hass(hass)
    hass.config.internal_url = "http://localhost:8123"
    with (
        # Mock a valid camera instance"
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
        patch("homeassistant.components.foscam.PLATFORMS", [Platform.SWITCH]),
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
