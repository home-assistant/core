"""Fixtures for the Collection Image integration tests."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_MEDIA_DIR_URI_1,
    MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
    MOCK_MEDIA_DIR_URI_EMPTY,
    MOCK_MEDIA_IMAGE_URI_1,
    TEST_IMAGE,
)
from .helpers import directory, image

from tests.common import MockConfigEntry


@dataclass
class MediaSourceState:
    """Configurable responses for the mocked media-source API."""

    browse_results: dict[str, BrowseMediaSource] = field(default_factory=dict)
    browse_exceptions: dict[str, Exception] = field(default_factory=dict)
    resolve_results: dict[str, PlayMedia] = field(default_factory=dict)
    resolve_exceptions: dict[str, Exception] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaSourceMocks:
    """Mocks installed for calls to the media-source API."""

    config_flow_browse: AsyncMock
    image_browse: AsyncMock
    resolve: AsyncMock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return the default collection-image config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Random Image",
        data={
            "media": {
                "media_content_id": MOCK_MEDIA_DIR_URI_1,
                "media_content_type": "",
            },
        },
    )


@pytest.fixture
def media_source_state() -> MediaSourceState:
    """Return default configurable responses for the media-source mock."""
    return MediaSourceState(
        browse_results={
            MOCK_MEDIA_DIR_URI_1: directory(
                "My pictures",
                BrowseMedia(
                    media_class=MediaClass.MUSIC,
                    media_content_id="media-source://mymedia/music",
                    media_content_type="audio/mp3",
                    title="a music track",
                    can_play=True,
                    can_expand=False,
                ),
                image(MOCK_MEDIA_IMAGE_URI_1),
            ),
            MOCK_MEDIA_DIR_URI_EMPTY: directory("Empty folder"),
        },
        browse_exceptions={
            MOCK_MEDIA_DIR_URI_BROWSE_ERROR: BrowseError(
                "Mock directory failed to browse"
            )
        },
        resolve_results={
            MOCK_MEDIA_IMAGE_URI_1: PlayMedia(
                url="",
                mime_type="image/png",
                path=TEST_IMAGE,
            ),
        },
    )


@pytest.fixture
def mock_media_source(
    media_source_state: MediaSourceState,
) -> Iterator[MediaSourceMocks]:
    """Patch media-source calls made by the collection-image integration."""

    async def browse_side_effect(
        _hass: HomeAssistant,
        media_content_id: str,
        *,
        content_filter=None,
    ) -> BrowseMediaSource:
        if exception := media_source_state.browse_exceptions.get(media_content_id):
            raise exception

        try:
            return media_source_state.browse_results[media_content_id]
        except KeyError as err:
            raise ValueError(
                f"Unexpected media content ID: {media_content_id}"
            ) from err

    async def resolve_side_effect(
        _hass: HomeAssistant,
        media_content_id: str,
        _entity_id: str,
    ) -> PlayMedia:
        if exception := media_source_state.resolve_exceptions.get(media_content_id):
            raise exception

        try:
            return media_source_state.resolve_results[media_content_id]
        except KeyError as err:
            raise ValueError(
                f"Unexpected media content ID: {media_content_id}"
            ) from err

    with (
        patch(
            "homeassistant.components.collection_image.config_flow.async_browse_media",
            new=AsyncMock(side_effect=browse_side_effect),
        ) as config_flow_browse,
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            new=AsyncMock(side_effect=browse_side_effect),
        ) as image_browse,
        patch(
            "homeassistant.components.collection_image.image.async_resolve_media",
            new=AsyncMock(side_effect=resolve_side_effect),
        ) as resolve,
    ):
        yield MediaSourceMocks(
            config_flow_browse=config_flow_browse,
            image_browse=image_browse,
            resolve=resolve,
        )
