"""The tests for the Collection Image image platform."""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.collection_image import DOMAIN
from homeassistant.components.image import Image, async_get_image
from homeassistant.components.media_source import PlayMedia, Unresolvable
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MediaSourceMocks, MediaSourceState
from .const import (
    DEFAULT_ENTITY_ID,
    MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
    MOCK_MEDIA_DIR_URI_EMPTY,
    MOCK_MEDIA_IMAGE_URI_1,
    TEST_IMAGE,
)
from .helpers import config_entry_from_uri

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

TEST_TIME = "2025-11-08T12:00:00+00:00"


async def _verify_path_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
):
    client = await hass_client()

    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    expected_data = await hass.async_add_executor_job(TEST_IMAGE.read_bytes)
    body = await resp.read()
    assert body == expected_data


@pytest.mark.usefixtures("mock_media_source")
async def test_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading an image."""
    with (
        freeze_time(TEST_TIME),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == TEST_TIME

    await _verify_path_image(hass, hass_client)


async def test_image_during_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_media_source: MediaSourceMocks,
) -> None:
    """Test loading an image, ensuring that we don't browse until after startup is complete."""
    with freeze_time(TEST_TIME):
        hass.set_state(CoreState.starting)

        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_media_source.image_browse.assert_not_called()
        mock_media_source.resolve.assert_not_called()

        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    mock_media_source.image_browse.assert_awaited_once()
    mock_media_source.resolve.assert_awaited_once()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == TEST_TIME

    await _verify_path_image(hass, hass_client)


@pytest.mark.usefixtures("mock_media_source")
async def test_image_url(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    media_source_state: MediaSourceState,
) -> None:
    """Test loading an image, when media resolves to a URL."""
    media_source_state.resolve_results[MOCK_MEDIA_IMAGE_URI_1] = PlayMedia(
        url="http://example.com/test.png",
        mime_type="image/png",
    )

    expected_data = await hass.async_add_executor_job(TEST_IMAGE.read_bytes)
    with (
        freeze_time(TEST_TIME),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == TEST_TIME

    client = await hass_client()

    with patch(
        "homeassistant.components.collection_image.image.CollectionImageImageEntity._async_load_image_from_url",
        new_callable=AsyncMock,
    ) as mock_load:
        mock_load.return_value = Image(
            content_type="image/png",
            content=expected_data,
        )
        resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
        mock_load.assert_awaited_once_with("http://example.com/test.png")

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    body = await resp.read()
    assert body == expected_data


@pytest.mark.usefixtures("mock_media_source")
async def test_no_images(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when there are no images in the media folder."""
    config_entry = config_entry_from_uri(MOCK_MEDIA_DIR_URI_EMPTY)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNAVAILABLE

    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        f"image.random_image: No valid images in {MOCK_MEDIA_DIR_URI_EMPTY}"
        in caplog.text
    )

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("mock_media_source")
async def test_media_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when media browse throws an error."""

    config_entry = config_entry_from_uri(MOCK_MEDIA_DIR_URI_BROWSE_ERROR)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNAVAILABLE

    await hass.async_block_till_done(wait_background_tasks=True)

    assert "image.random_image: Mock directory failed to browse" in caplog.text

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_unresolvable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_source_state: MediaSourceState,
    mock_media_source: MediaSourceMocks,
    caplog: pytest.LogCaptureFixture,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test when resolving an image fails."""
    media_source_state.resolve_exceptions[MOCK_MEDIA_IMAGE_URI_1] = Unresolvable(
        "Mock image failed to resolve"
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_media_source.image_browse.call_count == 1
    assert mock_media_source.resolve.call_count == 1

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNKNOWN

    await hass.async_block_till_done(wait_background_tasks=True)

    assert "image.random_image: Mock image failed to resolve" in caplog.text

    # Test we can recover by calling shuffle again when the image is resolvable
    del media_source_state.resolve_exceptions[MOCK_MEDIA_IMAGE_URI_1]

    with (
        freeze_time(TEST_TIME),
    ):
        await hass.services.async_call(
            DOMAIN,
            "shuffle",
            {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID},
            blocking=True,
        )

    assert mock_media_source.image_browse.call_count == 2
    assert mock_media_source.resolve.call_count == 2

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == TEST_TIME

    await _verify_path_image(hass, hass_client)


@pytest.mark.usefixtures("mock_media_source")
async def test_image_file_read_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_source_state: MediaSourceState,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that a file read error is surfaced when serving the image."""
    missing_path = Path(__file__).parent / "does_not_exist.png"
    media_source_state.resolve_results[MOCK_MEDIA_IMAGE_URI_1] = PlayMedia(
        url="",
        mime_type="image/png",
        path=missing_path,
    )

    with (
        freeze_time(TEST_TIME),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Browse and resolve succeeded, so the entity is available with an image.
    state = hass.states.get(DEFAULT_ENTITY_ID)
    assert state and state.state == TEST_TIME

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_image(hass, DEFAULT_ENTITY_ID)
    assert exc_info.value.translation_key == "image_read_error"
    assert exc_info.value.translation_placeholders["path"] == str(missing_path)

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
