"""Test ai_task media source."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task.media_source import async_get_media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_local_media_source(hass: HomeAssistant, init_components: None) -> None:
    """Test that the image media source is created."""
    item = await media_source.async_browse_media(hass, "media-source://")

    assert any(c.title == "AI Generated Images" for c in item.children)

    source = await async_get_media_source(hass)
    assert isinstance(source, media_source.local_source.LocalSource)
    assert source.name == "AI Generated Images"
    assert source.domain == "ai_task"
    assert list(source.media_dirs) == ["image"]
    # Depending on Docker, the default is one of the two paths
    assert source.media_dirs["image"] in (
        "/media/ai_task/image",
        hass.config.path("media/ai_task/image"),
    )
    assert source.url_prefix == "/ai_task"

    hass.config.media_dirs = {}

    with pytest.raises(
        HomeAssistantError,
        match="AI Task media source requires at least one media directory configured",
    ):
        await async_get_media_source(hass)


async def test_browse_media_directory_not_exist_error(
    hass: HomeAssistant, init_components: None
) -> None:
    """Test browsing AI task media source when directory doesn't exist."""
    source = await async_get_media_source(hass)

    with patch.object(Path, "exists", return_value=False):
        item = media_source.MediaSourceItem(hass, "ai_task", "image/", None)

        with pytest.raises(BrowseError) as excinfo:
            await source.async_browse_media(item)

        error_message = str(excinfo.value)
        assert "No AI-generated images found" in error_message
        assert "ai_task.generate_image" in error_message
