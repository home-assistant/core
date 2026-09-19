"""Test the Immich Frames integration setup."""

from unittest.mock import patch

from homeassistant.components.immich_frames.const import (
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
)
from homeassistant.components.immich_frames.coordinator import ImmichFramesData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_creates_image(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test that setup creates a usable image entity."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Living room",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Living room",
        },
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.immich.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data.data, ImmichFramesData)
    assert hass.states.get("image.living_room_image").state != "unknown"
    assert entry.runtime_data.api.assets.async_view_asset.await_count == 1
