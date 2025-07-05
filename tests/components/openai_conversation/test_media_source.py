"""Test openai_conversation media source."""

import pytest

from homeassistant.components import media_source
from homeassistant.components.openai_conversation.const import ImageData
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()


async def _mock_image_generate(hass: HomeAssistant) -> str:
    """Mock image generation and return the image_id."""
    assert await async_setup_component(hass, "openai_conversation", {})
    await hass.async_block_till_done()
    IMAGE_STORAGE = hass.data.setdefault("openai_conversation", {})
    filename = "1700000000_0.png"
    IMAGE_STORAGE[filename] = ImageData(
        data=b"A",
        timestamp=1700000000,
        mime_type="image/png",
        title="Mock Image",
    )
    return filename


async def test_browsing(hass: HomeAssistant) -> None:
    """Test browsing image media source."""
    image_id = await _mock_image_generate(hass)

    item = await media_source.async_browse_media(
        hass, "media-source://openai_conversation"
    )

    assert item is not None
    assert item.title == "OpenAI Generated Images"
    assert len(item.children) == 1
    assert item.children[0].media_content_type == "image/png"
    assert item.children[0].identifier == image_id
    assert item.children[0].title == "Mock Image"
    assert (
        item.children[0].thumbnail == f"/api/openai_conversation/thumbnails/{image_id}"
    )

    with pytest.raises(
        media_source.BrowseError,
        match="Unknown item",
    ):
        await media_source.async_browse_media(
            hass, "media-source://openai_conversation/invalid_path"
        )


async def test_resolving(hass: HomeAssistant) -> None:
    """Test resolving."""
    image_id = await _mock_image_generate(hass)
    item = await media_source.async_resolve_media(
        hass, f"media-source://openai_conversation/{image_id}", None
    )
    assert item is not None
    assert item.url == f"/api/openai_conversation/images/{image_id}"
    assert item.mime_type == "image/png"

    invalid_id = "aabbccddeeff"
    with pytest.raises(
        media_source.Unresolvable,
        match=f"Could not resolve media item: {invalid_id}",
    ):
        await media_source.async_resolve_media(
            hass, f"media-source://openai_conversation/{invalid_id}", None
        )
