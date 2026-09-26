"""Test Immich Frames diagnostics."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.immich_frames.const import (
    CONF_ALBUM_IDS,
    CONF_FRAME_ID,
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
            CONF_FRAME_ID: "private-frame",
        },
        options={
            CONF_ALBUM_IDS: ["private-album"],
            CONF_SMART_QUERY: "private person",
        },
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
    assert diagnostics["entry"]["entry_id"] == "**REDACTED**"
    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_IMMICH_ENTRY_ID] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_FRAME_NAME] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_FRAME_ID] == "**REDACTED**"
    assert diagnostics["entry"]["options"][CONF_ALBUM_IDS] == "**REDACTED**"


async def test_diagnostics_handle_unavailable_frame(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test diagnostics remain available before a frame has rendered."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Empty frame",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Empty frame",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch("homeassistant.components.immich.async_setup_entry", return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["frame"] == {"status": "unavailable"}
