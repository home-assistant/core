"""Test ai_task media source."""

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant


async def test_local_media_source(hass: HomeAssistant, init_components: None) -> None:
    """Test that the image media source is created."""
    item = await media_source.async_browse_media(hass, "media-source://")

    assert any(c.title == "AI Generated Images" for c in item.children)
