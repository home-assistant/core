"""Test ai_task media source."""

import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task import ImageData
from homeassistant.core import HomeAssistant


@pytest.fixture(name="image_id")
async def mock_image_generate(hass: HomeAssistant) -> str:
    """Mock image generation and return the image_id."""
    image_storage = hass.data.setdefault("ai_task_images", {})
    filename = "2025-06-15_150640_test_task.png"
    image_storage[filename] = ImageData(
        data=b"A",
        timestamp=1750000000,
        mime_type="image/png",
        title="Mock Image",
    )
    return filename


async def test_browsing(
    hass: HomeAssistant, init_components: None, image_id: str
) -> None:
    """Test browsing image media source."""
    item = await media_source.async_browse_media(hass, "media-source://ai_task")

    assert item is not None
    assert item.title == "AI Generated Images"
    assert len(item.children) == 1
    assert item.children[0].media_content_type == "image/png"
    assert item.children[0].identifier == image_id
    assert item.children[0].title == "Mock Image"

    with pytest.raises(
        media_source.BrowseError,
        match="Unknown item",
    ):
        await media_source.async_browse_media(
            hass, "media-source://ai_task/invalid_path"
        )


async def test_resolving(
    hass: HomeAssistant, init_components: None, image_id: str
) -> None:
    """Test resolving."""
    item = await media_source.async_resolve_media(
        hass, f"media-source://ai_task/{image_id}", None
    )
    assert item is not None
    assert item.url == f"/api/ai_task/images/{image_id}"
    assert item.mime_type == "image/png"

    invalid_id = "aabbccddeeff"
    with pytest.raises(
        media_source.Unresolvable,
        match=f"Could not resolve media item: {invalid_id}",
    ):
        await media_source.async_resolve_media(
            hass, f"media-source://ai_task/{invalid_id}", None
        )
