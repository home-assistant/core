"""Test the Foscam number platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry, snapshot_platform


async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the number entities (volume controls) are correctly created and registered."""
    entry = MockConfigEntry(
        domain="foscam",
        data=VALID_CONFIG,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.foscam.PLATFORMS", [Platform.NUMBER]),
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_class,
    ):
        mock_foscam_instance = setup_mock_foscam_camera(mock_foscam_class)

        mock_foscam_instance.supports_speak_volume_adjustment = True

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
