"""Fixtures for the Collection Image integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia

from .const import TEST_IMAGE

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return the default collection-image config entry."""
    return MockConfigEntry(
        data={
            "media": {
                "media_content_id": "media-source://mymedia",
                "media_content_type": "",
            },
        },
        domain=DOMAIN,
        title="Random Image",
    )


@pytest.fixture
def browse_media_result() -> BrowseMediaSource:
    """Return a default collection containing one image."""
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
def mock_media_source(browse_media_result: BrowseMediaSource):
    """Mock browsing and resolving the configured media source."""
    with (
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            new=AsyncMock(return_value=browse_media_result),
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
