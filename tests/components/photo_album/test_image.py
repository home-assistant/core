"""The tests for the Photo Frame image platform."""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.components.photo_frame.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test loading an image."""
    with freeze_time("2025-11-08T12:00:00.000"):
        config_entry = MockConfigEntry(
            data={
                "name": "Random Image",
                "media": {
                    "media_content_id": "media-source://mymedia",
                    "media_content_type": "",
                },
            },
            domain=DOMAIN,
            title="Random Image",
        )

        with (
            patch(
                "homeassistant.components.photo_frame.image.async_browse_media",
                return_value=BrowseMediaSource(
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
                ),
            ),
            patch(
                "homeassistant.components.photo_frame.image.async_resolve_media",
                return_value=PlayMedia(
                    url="fake",
                    mime_type="image/png",
                    path=Path(__file__).parent / "test.png",
                ),
            ),
        ):
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    state = hass.states.get("image.random_image")

    assert state and state.state == "2025-11-08T12:00:00+00:00"

    client = await hass_client()

    resp = await client.get("/api/image_proxy/image.random_image")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    image_path = Path(__file__).parent / "test.png"
    expected_data = await hass.async_add_executor_job(image_path.read_bytes)
    body = await resp.read()
    assert body == expected_data


async def test_image_during_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test loading an image, ensuring that we don't browse until after startup is complete."""
    with freeze_time("2025-11-08T12:00:00.000"):
        hass.set_state(CoreState.starting)
        config_entry = MockConfigEntry(
            data={
                "name": "Random Image",
                "media": {
                    "media_content_id": "media-source://mymedia",
                    "media_content_type": "",
                },
            },
            domain=DOMAIN,
            title="Random Image",
        )

        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        with (
            patch(
                "homeassistant.components.photo_frame.image.async_browse_media",
                return_value=BrowseMediaSource(
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
                ),
            ),
            patch(
                "homeassistant.components.photo_frame.image.async_resolve_media",
                return_value=PlayMedia(
                    url="fake",
                    mime_type="image/png",
                    path=Path(__file__).parent / "test.png",
                ),
            ),
        ):
            hass.set_state(CoreState.running)
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
            await hass.async_block_till_done()

    state = hass.states.get("image.random_image")

    assert state and state.state == "2025-11-08T12:00:00+00:00"

    client = await hass_client()

    resp = await client.get("/api/image_proxy/image.random_image")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    image_path = Path(__file__).parent / "test.png"
    expected_data = await hass.async_add_executor_job(image_path.read_bytes)
    body = await resp.read()
    assert body == expected_data


async def test_no_images(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when there are no images in the media folder."""
    with freeze_time("2025-11-08T12:00:00.000"):
        config_entry = MockConfigEntry(
            data={
                "name": "Random No Image",
                "media": {
                    "media_content_id": "media-source://mymedia/nopictures",
                    "media_content_type": "",
                },
            },
            domain=DOMAIN,
            title="Random No Image",
        )

        with patch(
            "homeassistant.components.photo_frame.image.async_browse_media",
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

    state = hass.states.get("image.random_no_image")

    assert state and state.state == "2025-11-08T12:00:00+00:00"

    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "image.random_no_image: No valid images in media-source://mymedia/nopictures"
        in caplog.text
    )

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.random_no_image")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_media_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when media browse throws an error."""
    with freeze_time("2025-11-08T12:00:00.000"):
        config_entry = MockConfigEntry(
            data={
                "name": "Random No Image",
                "media": {
                    "media_content_id": "media-source://badpath",
                    "media_content_type": "",
                },
            },
            domain=DOMAIN,
            title="Random No Image",
        )

        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("image.random_no_image")

    assert state and state.state == "2025-11-08T12:00:00+00:00"

    await hass.async_block_till_done(wait_background_tasks=True)

    assert "image.random_no_image: Media Source not loaded" in caplog.text

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.random_no_image")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
