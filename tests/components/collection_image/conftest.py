"""Fixtures for the Collection Image integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_MEDIA_URI_1,
    MOCK_MEDIA_URI_2,
    MOCK_MEDIA_URI_BROWSE_ERROR,
    MOCK_MEDIA_URI_EMPTY,
    TEST_IMAGE,
)

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
    """Return the default collection containing one image."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title="My pictures",
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
def browse_media_result_2() -> BrowseMediaSource:
    """Return a collection containing three images."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title="Three images",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.IMAGE,
                media_content_id=f"media-source://mymedia_2/photo_{number}",
                media_content_type="image/png",
                title=f"picture {number}",
                can_play=True,
                can_expand=False,
            )
            for number in range(1, 4)
        ],
    )


@pytest.fixture
def browse_media_result_empty() -> BrowseMediaSource:
    """Return a collection containing nothing."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title="Empty folder",
        can_play=False,
        can_expand=True,
        children=[],
    )


@pytest.fixture
def browse_media_browse_error() -> BrowseMediaSource:
    """Throws a BrowseError."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title="My pictures",
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
def mock_media_source(
    browse_media_result: BrowseMediaSource,
    browse_media_result_2: BrowseMediaSource,
    browse_media_result_empty: BrowseMediaSource,
):
    """Mock browsing and resolving the configured media source."""

    async def browse_side_effect(
        _hass: HomeAssistant,
        media_content_id,
        *,
        content_filter=None,
    ):
        if media_content_id == MOCK_MEDIA_URI_1:
            return browse_media_result

        if media_content_id == MOCK_MEDIA_URI_2:
            return browse_media_result_2

        if media_content_id == MOCK_MEDIA_URI_EMPTY:
            return browse_media_result_empty

        if media_content_id == MOCK_MEDIA_URI_BROWSE_ERROR:
            raise BrowseError("Mock directory failed to browse")

        raise ValueError(f"Unexpected media content ID: {media_content_id}")

    with (
        patch(
            "homeassistant.components.collection_image.config_flow.async_browse_media",
            new=AsyncMock(side_effect=browse_side_effect),
        ) as mock_config_flow_browse,
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            new=AsyncMock(side_effect=browse_side_effect),
        ) as mock_image_browse,
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
        yield mock_config_flow_browse, mock_image_browse, mock_resolve
