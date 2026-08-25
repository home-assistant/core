"""Tests for the Collection Image integration services."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.collection_image.image import CollectionImageImageEntity
from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "image.random_image"
TEST_IMAGE = Path(__file__).parent / "test.png"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a Collection Image config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Random Image",
        data={
            "media": {
                "media_content_id": "media-source://mymedia",
                "media_content_type": "",
            }
        },
    )


@pytest.fixture
def browse_media() -> BrowseMediaSource:
    """Return a media folder containing one image and one non-image."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title="",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="media-source://mymedia/music",
                media_content_type="audio/mp3",
                title="a music track",
                can_play=True,
                can_expand=False,
            ),
            BrowseMedia(
                media_class=MediaClass.IMAGE,
                media_content_id="media-source://mymedia/photo",
                media_content_type="image/png",
                title="a picture",
                can_play=True,
                can_expand=False,
            ),
        ],
    )


@pytest.fixture
def mock_media_source(browse_media: BrowseMediaSource):
    """Mock browsing and resolving the configured media source."""
    with (
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            new=AsyncMock(return_value=browse_media),
        ) as mock_browse,
        patch(
            "homeassistant.components.collection_image.image.async_resolve_media",
            new=AsyncMock(
                return_value=PlayMedia(
                    url="",
                    mime_type="image/png",
                    path=TEST_IMAGE,
                )
            ),
        ) as mock_resolve,
    ):
        yield mock_browse, mock_resolve


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Collection Image integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_shuffle_action(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_media_source,
) -> None:
    """Test that shuffle calls get_next_image on the target entity."""
    await _setup_integration(hass, config_entry)

    with patch.object(
        CollectionImageImageEntity,
        "get_next_image",
        new_callable=AsyncMock,
    ) as mock_get_next_image:
        await hass.services.async_call(
            DOMAIN,
            "shuffle",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_get_next_image.assert_awaited_once()
