"""Test Immich Frames diagnostics."""

from unittest.mock import patch

from homeassistant.components.immich_frames.const import (
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_SMART_QUERY,
)
from homeassistant.components.immich_frames.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics_exclude_image_bytes(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test diagnostics contain metadata but never the image content."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Living room",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Living room",
        },
        options={CONF_SMART_QUERY: "private person"},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.immich.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["frame"]["image_bytes"] > 0
    assert "image" not in diagnostics["frame"]
    assert "asset_id" not in diagnostics["frame"]
    assert "local_datetime" not in diagnostics["frame"]
    assert diagnostics["entry"]["options"][CONF_SMART_QUERY] == "**REDACTED**"
