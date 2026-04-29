"""Test ai_task media source."""

from unittest.mock import patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task.const import DATA_MEDIA_SOURCE
from homeassistant.components.ai_task.media_source import async_get_media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_local_media_source(hass: HomeAssistant, init_components: None) -> None:
    """Test the image media source is only registered once an image is generated."""
    # The image folder does not exist yet, so the media source should not be
    # listed as a top-level media source.
    item = await media_source.async_browse_media(hass, "media-source://")
    assert not any(c.title == "AI generated images" for c in item.children)

    # async_get_media_source returns None to defer registration.
    assert await async_get_media_source(hass) is None

    # The local source is still configured internally so image generation can
    # use it to upload new images.
    source = hass.data[DATA_MEDIA_SOURCE]
    assert isinstance(source, media_source.local_source.LocalSource)
    assert source.name == "AI generated images"
    assert source.domain == "ai_task"
    assert list(source.media_dirs) == ["image"]
    # Depending on Docker, the default is one of the two paths
    assert source.media_dirs["image"] in (
        "/media/ai_task/image",
        hass.config.path("media/ai_task/image"),
    )
    assert source.url_prefix == "/ai_task"

    # Once an image has been generated and the folder exists, the source is
    # returned.
    with patch(
        "homeassistant.components.ai_task.media_source.Path.exists",
        return_value=True,
    ):
        result = await async_get_media_source(hass)
    assert result is hass.data[DATA_MEDIA_SOURCE]
    assert isinstance(result, media_source.local_source.LocalSource)

    hass.config.media_dirs = {}

    with pytest.raises(
        HomeAssistantError,
        match="AI Task media source requires at least one media directory configured",
    ):
        await async_get_media_source(hass)
