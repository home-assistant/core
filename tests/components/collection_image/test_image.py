"""The tests for the Collection Image image platform."""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.image import Image, async_get_image
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_ENTITY_ID, TEST_IMAGE

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

TEST_TIME = "2025-11-08T12:00:00+00:00"


async def test_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_media_source,
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

    client = await hass_client()

    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    expected_data = await hass.async_add_executor_job(TEST_IMAGE.read_bytes)
    body = await resp.read()
    assert body == expected_data


async def test_image_during_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_media_source,
) -> None:
    """Test loading an image, ensuring that we don't browse until after startup is complete."""
    with freeze_time(TEST_TIME):
        hass.set_state(CoreState.starting)

        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == TEST_TIME

    client = await hass_client()

    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    expected_data = await hass.async_add_executor_job(TEST_IMAGE.read_bytes)
    body = await resp.read()
    assert body == expected_data


async def test_image_url(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    browse_media_result: BrowseMediaSource,
) -> None:
    """Test loading an image, when media resolves to a URL."""

    expected_data = await hass.async_add_executor_job(TEST_IMAGE.read_bytes)

    with (
        freeze_time(TEST_TIME),
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            return_value=browse_media_result,
        ),
        patch(
            "homeassistant.components.collection_image.image.async_resolve_media",
            return_value=PlayMedia(
                url="http://example.com/test.png",
                mime_type="image/png",
            ),
        ),
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


async def test_no_images(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when there are no images in the media folder."""
    with patch(
        "homeassistant.components.collection_image.image.async_browse_media",
        return_value=BrowseMediaSource(
            domain=None,
            identifier=None,
            media_class="",
            media_content_type="",
            title="",
            can_play=False,
            can_expand=True,
            children=[],
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNAVAILABLE

    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "image.random_image: No valid images in media-source://mymedia" in caplog.text
    )

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_media_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when media browse throws an error."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNAVAILABLE

    await hass.async_block_till_done(wait_background_tasks=True)

    assert "image.random_image: Media Source not loaded" in caplog.text

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{DEFAULT_ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_unresolvable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    browse_media_result: BrowseMediaSource,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when resolving an image fails."""

    with (
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            return_value=browse_media_result,
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(DEFAULT_ENTITY_ID)

    assert state and state.state == STATE_UNAVAILABLE

    await hass.async_block_till_done(wait_background_tasks=True)

    assert "image.random_image: Media Source not loaded" in caplog.text


async def test_image_file_read_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    browse_media_result: BrowseMediaSource,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that a file read error is surfaced when serving the image."""
    missing_path = Path(__file__).parent / "does_not_exist.png"

    with (
        freeze_time(TEST_TIME),
        patch(
            "homeassistant.components.collection_image.image.async_browse_media",
            return_value=browse_media_result,
        ),
        patch(
            "homeassistant.components.collection_image.image.async_resolve_media",
            return_value=PlayMedia(
                url="",
                mime_type="image/png",
                path=missing_path,
            ),
        ),
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
