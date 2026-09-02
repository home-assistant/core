"""Tests for the Collection Image integration services."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.collection_image.image import CollectionImageImageEntity
from homeassistant.components.collection_image.services import (
    CollectionImageService,
    CollectionImageServiceArgument,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MediaSourceMocks, MediaSourceState
from .const import DEFAULT_ENTITY_ID, MOCK_MEDIA_DIR_URI_1
from .helpers import directory, image

from tests.common import Mock, MockConfigEntry


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
    """Test that shuffle calls get_random_image on the target entity."""
    await _setup_integration(hass, config_entry)

    with patch.object(
        CollectionImageImageEntity,
        "get_random_image",
        new_callable=AsyncMock,
    ) as mock_get_random_image:
        await hass.services.async_call(
            DOMAIN,
            "shuffle",
            {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID},
            blocking=True,
        )

    mock_get_random_image.assert_awaited_once()


async def test_navigation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_source_state: MediaSourceState,
    mock_media_source: MediaSourceMocks,
) -> None:
    """Test first/last/next/previous actions."""

    images = [
        image("media-source://mymedia/1"),
        image("media-source://mymedia/2"),
        image("media-source://mymedia/3"),
    ]

    media_source_state.browse_results = {
        MOCK_MEDIA_DIR_URI_1: directory("My pictures", *images)
    }
    media_source_state.resolve_results = {
        img.media_content_id: PlayMedia(
            url="",
            mime_type="image/png",
        )
        for img in images
    }

    with patch(
        "homeassistant.components.collection_image.image.random.choice",
        new=Mock(return_value=images[1]),
    ):
        await _setup_integration(hass, config_entry)
        await hass.async_block_till_done()

    assert mock_media_source.image_browse.call_count == 1
    assert mock_media_source.resolve.call_count == 1

    def assert_resolve_index(idx: int):
        args, _kwargs = mock_media_source.resolve.call_args
        assert args[1] == images[idx].media_content_id

    assert_resolve_index(1)

    steps = (
        (CollectionImageService.SELECT_FIRST, 0),
        (CollectionImageService.SELECT_LAST, 2),
        (CollectionImageService.SELECT_PREVIOUS, 1),
        (CollectionImageService.SELECT_PREVIOUS, 0),
        (CollectionImageService.SELECT_PREVIOUS, 0),
        (CollectionImageService.SELECT_PREVIOUS, 2, True),
        (CollectionImageService.SELECT_PREVIOUS, 1, True),
        (CollectionImageService.SELECT_PREVIOUS, 0, True),
        (CollectionImageService.SELECT_NEXT, 1),
        (CollectionImageService.SELECT_NEXT, 2),
        (CollectionImageService.SELECT_NEXT, 2),
        (CollectionImageService.SELECT_NEXT, 0, True),
        (CollectionImageService.SELECT_NEXT, 1, True),
    )

    for service, expected_index, *wrap_arg in steps:
        data = {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID}
        if wrap_arg:
            data[CollectionImageServiceArgument.WRAP] = True
        await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
        )
        assert_resolve_index(expected_index)

    # Change to new images and verify that next resets count to 0
    images = [
        image("media-source://mymedia/4"),
        image("media-source://mymedia/5"),
        image("media-source://mymedia/6"),
    ]

    media_source_state.browse_results = {
        MOCK_MEDIA_DIR_URI_1: directory("My pictures", *images)
    }
    media_source_state.resolve_results = {
        img.media_content_id: PlayMedia(
            url="",
            mime_type="image/png",
        )
        for img in images
    }

    data = {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID}
    await hass.services.async_call(
        DOMAIN,
        CollectionImageService.SELECT_NEXT,
        data,
        blocking=True,
    )
    assert_resolve_index(0)

    # Change to new images and verify that previous resets count to -1
    images = [
        image("media-source://mymedia/7"),
        image("media-source://mymedia/8"),
        image("media-source://mymedia/9"),
    ]

    media_source_state.browse_results = {
        MOCK_MEDIA_DIR_URI_1: directory("My pictures", *images)
    }
    media_source_state.resolve_results = {
        img.media_content_id: PlayMedia(
            url="",
            mime_type="image/png",
        )
        for img in images
    }

    data = {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID}
    await hass.services.async_call(
        DOMAIN,
        CollectionImageService.SELECT_PREVIOUS,
        data,
        blocking=True,
    )
    assert_resolve_index(2)

    # Now there are no images, go to unavailable
    media_source_state.browse_results = {MOCK_MEDIA_DIR_URI_1: directory("My pictures")}
    await hass.services.async_call(
        DOMAIN,
        CollectionImageService.SELECT_NEXT,
        data,
        blocking=True,
    )

    state = hass.states.get(DEFAULT_ENTITY_ID)
    assert state and state.state == STATE_UNAVAILABLE


async def test_first_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_source_state: MediaSourceState,
    mock_media_source: MediaSourceMocks,
) -> None:
    """Check that calling first on empty directory sets unavailable."""
    images = [
        image("media-source://mymedia/1"),
    ]
    media_source_state.browse_results = {
        MOCK_MEDIA_DIR_URI_1: directory("My pictures", *images)
    }
    media_source_state.resolve_results = {
        img.media_content_id: PlayMedia(
            url="",
            mime_type="image/png",
        )
        for img in images
    }
    await _setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)
    assert state and state.state != STATE_UNAVAILABLE

    media_source_state.browse_results = {MOCK_MEDIA_DIR_URI_1: directory("My pictures")}
    await hass.services.async_call(
        DOMAIN,
        CollectionImageService.SELECT_FIRST,
        {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(DEFAULT_ENTITY_ID)
    assert state and state.state == STATE_UNAVAILABLE
