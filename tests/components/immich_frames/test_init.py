"""Test the Immich Frames integration setup."""

from copy import copy
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from aioimmich.assets.models import ExifInfo
from aioimmich.exceptions import ImmichError, ImmichUnauthorizedError
import pytest

from homeassistant.components.immich_frames import (
    async_migrate_entry,
    async_remove_entry,
    async_setup_entry,
)
from homeassistant.components.immich_frames.const import (
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_PHOTO_FIT,
    CONF_SOURCE,
    DEFAULT_SOURCE,
    PHOTO_FIT_CROP,
)
from homeassistant.components.immich_frames.coordinator import (
    ImmichFramesData,
    ImmichFramesDataUpdateCoordinator,
)
from homeassistant.components.immich_frames.selection import UnsupportedSourceError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.immich import const as immich_const

MOCK_SEARCH_ASSETS = immich_const.MOCK_SEARCH_ASSETS


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


async def test_setup_entry_translates_parent_not_ready(
    hass: HomeAssistant,
) -> None:
    """A frame retries until its parent Immich entry is loaded."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Waiting frame",
        data={CONF_IMMICH_ENTRY_ID: "missing-parent"},
    )
    entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady) as exc_info:
        await async_setup_entry(hass, entry)

    assert exc_info.value.translation_key == "immich_not_ready"


async def test_remove_entry_clears_cached_image(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Deleting a frame removes its private cached image."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Cached frame",
        data={CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id},
    )
    entry.add_to_hass(hass)
    cache_path = hass.config.path(".storage", f"immich_frames_{entry.entry_id}.json")
    await hass.async_add_executor_job(lambda: Path(cache_path).write_text("cached"))

    await async_remove_entry(hass, entry)

    assert not await hass.async_add_executor_job(lambda: Path(cache_path).exists())


async def test_migrate_entry_adds_default_source(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Version one entries gain the current default source."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Migrated frame",
        data={CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.data[CONF_SOURCE] == DEFAULT_SOURCE
    assert entry.data[CONF_IMMICH_ENTRY_ID] == parent_immich_entry.entry_id


async def test_coordinator_uses_cache_and_controls(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test cached fallback and navigation controls."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Cache controls",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Cache controls",
        },
    )
    entry.add_to_hass(hass)
    coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
    cached = (MOCK_SEARCH_ASSETS[0], b"cached", dt_util.utcnow())
    with patch.object(coordinator._cache, "read", return_value=cached):
        await coordinator._async_setup()
    assert coordinator.data is not None
    assert coordinator.data.using_cache is True

    coordinator.paused = True
    assert await coordinator._async_update_data() is coordinator.data
    coordinator.paused = False
    with patch(
        "homeassistant.components.immich_frames.coordinator.async_get_candidates",
        new=AsyncMock(return_value=[]),
    ):
        result = await coordinator._async_update_data()
    assert result.status == "no_matching_photos"
    assert result.connected is True

    with patch.object(coordinator._cache, "clear") as clear_cache:
        await coordinator.async_clear_cache()
        clear_cache.assert_called_once()


async def test_coordinator_starts_parent_reauth_and_translates_unsupported_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Authentication remains actionable while unsupported sources are cached."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Error paths",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Error paths",
        },
    )
    entry.add_to_hass(hass)
    coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(
                side_effect=ImmichUnauthorizedError(
                    {"message": "bad", "correlationId": "test"}
                )
            ),
        ),
        patch.object(parent_immich_entry, "async_start_reauth") as start_reauth,
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()
    start_reauth.assert_called_once_with(hass)

    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(
                side_effect=ImmichError(
                    {"message": "server error", "correlationId": "test"}
                )
            ),
        ),
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "upstream_error"

    parent_immich_entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "immich_not_ready"
    parent_immich_entry.mock_state(hass, ConfigEntryState.LOADED)

    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(side_effect=UnsupportedSourceError("memories")),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_covers_recovery_and_render_error_paths(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test recoverable upstream, render, cache, and control paths."""
    coordinator = _coordinator_for_test(hass, parent_immich_entry)
    coordinator._connected = False
    portrait = copy(MOCK_SEARCH_ASSETS[0])
    portrait.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    coordinator.options["mode"] = "pairs"
    coordinator.options[CONF_PHOTO_FIT] = PHOTO_FIT_CROP
    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(return_value=[portrait]),
        ),
        patch(
            "homeassistant.components.immich_frames.coordinator.render",
            return_value=(b"rendered", "single"),
        ) as render,
        patch.object(coordinator._cache, "write", side_effect=OSError("read-only")),
    ):
        result = await coordinator._async_update_data()
    assert result.status == "ready"
    assert render.call_args.args[2] == PHOTO_FIT_CROP

    with patch(
        "homeassistant.components.immich_frames.coordinator.async_get_candidates",
        new=AsyncMock(side_effect=ClientError("down")),
    ):
        result = await coordinator._async_update_data()
    assert result.status == "upstream_unavailable"
    with patch(
        "homeassistant.components.immich_frames.coordinator.async_get_candidates",
        new=AsyncMock(side_effect=LookupError("none")),
    ):
        result = await coordinator._async_update_data()
    assert result.status == "no_matching_photos"
    with (
        patch(
            "homeassistant.components.immich_frames.coordinator.async_get_candidates",
            new=AsyncMock(return_value=[portrait]),
        ),
        patch(
            "homeassistant.components.immich_frames.coordinator.render",
            side_effect=ValueError("bad"),
        ),
    ):
        result = await coordinator._async_update_data()
    assert result.status == "invalid_image"

    with (
        patch.object(coordinator, "async_refresh", new=AsyncMock()) as refresh,
        patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload,
    ):
        await coordinator.async_refresh_now()
        await coordinator.async_next()
        coordinator.async_update_settings({"interval": 60})
        assert refresh.await_count == 2
        schedule_reload.assert_called_once()
    assert coordinator._orientation_is_portrait(portrait) is True
    assert coordinator._orientation_is_portrait(MOCK_SEARCH_ASSETS[0]) is False


def _coordinator_for_test(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> ImmichFramesDataUpdateCoordinator:
    """Create a coordinator with one cached data item."""
    entry = MockConfigEntry(
        domain="immich_frames",
        title="Coordinator test",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Coordinator test",
        },
    )
    entry.add_to_hass(hass)
    coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
    coordinator.data = ImmichFramesData(
        asset=MOCK_SEARCH_ASSETS[0],
        image=b"cached",
        updated_at=dt_util.utcnow(),
    )
    return coordinator
