"""Test ai_task media source."""

import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task.media_source import async_get_media_source
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
