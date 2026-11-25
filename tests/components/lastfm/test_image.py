"""Tests for the Last.fm image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pylast import MalformedResponseError, NetworkError, PyLastError, Track, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator
import respx

from homeassistant.const import ATTR_ENTITY_PICTURE, Platform
from homeassistant.core import HomeAssistant

from . import COVER_IMAGE, MockNetwork, MockUser, mock_track
from .conftest import ComponentSetup

ENTITY_ID = "image.lastfm_testaccount1_now_playing"
OTHER_COVER_IMAGE = "https://lastfm.freetls.fastly.net/i/u/300x300/other.png"


@pytest.fixture(autouse=True)
def image_only() -> Generator[None]:
    """Enable only the image platform."""
    with patch("homeassistant.components.lastfm.PLATFORMS", [Platform.IMAGE]):
        yield


async def _async_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, user: MockUser
) -> None:
    """Run one coordinator update with the given user."""
    with patch("pylast.User", return_value=user):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


async def _async_get_image(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> tuple[HTTPStatus, bytes]:
    """Return the status and body of the image served by Home Assistant."""
    client = await hass_client()
    resp = await client.get(hass.states.get(ENTITY_ID).attributes[ATTR_ENTITY_PICTURE])
    return resp.status, await resp.read()


@respx.mock
async def test_now_playing_image(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the image shows the album art of the playing track."""
    freezer.move_to("2026-11-25T00:00:00+00:00")
    respx.get(COVER_IMAGE).respond(content_type="image/png", content=b"cover")
    respx.get(OTHER_COVER_IMAGE).respond(content_type="image/png", content=b"other")

    await setup_integration(config_entry, default_user)

    assert hass.states.get(ENTITY_ID).state == "2026-11-25T00:00:00+00:00"
    assert await _async_get_image(hass, hass_client) == (HTTPStatus.OK, b"cover")

    other_track = Track(
        "other artist",
        "other title",
        MockNetwork("lastfm"),
        info={"image": ["small", "medium", "large", OTHER_COVER_IMAGE]},
    )
    await _async_update(hass, freezer, MockUser(now_playing_result=other_track))

    assert hass.states.get(ENTITY_ID).state == "2026-11-25T00:00:30+00:00"
    assert await _async_get_image(hass, hass_client) == (HTTPStatus.OK, b"other")


@pytest.mark.parametrize(
    "user",
    [
        pytest.param(MockUser(), id="not_playing"),
        pytest.param(MockUser(now_playing_result=mock_track([])), id="no_album_art"),
    ],
)
async def test_no_album_art(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    user: MockUser,
) -> None:
    """Test no image is served without album art for the playing track."""
    await setup_integration(config_entry, user)

    status, _ = await _async_get_image(hass, hass_client)
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.parametrize(
    "user",
    [
        pytest.param(MockUser(), id="stopped_playing"),
        pytest.param(
            MockUser(
                now_playing_result=Track(
                    "other artist",
                    "other title",
                    MockNetwork("lastfm"),
                    info={"image": []},
                )
            ),
            id="no_album_art",
        ),
    ],
)
@respx.mock
async def test_album_art_cleared(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    user: MockUser,
) -> None:
    """Test the previous album art is no longer served once it is gone."""
    respx.get(COVER_IMAGE).respond(content_type="image/png", content=b"cover")

    await setup_integration(config_entry, default_user)
    assert await _async_get_image(hass, hass_client) == (HTTPStatus.OK, b"cover")

    await _async_update(hass, freezer, user)

    status, _ = await _async_get_image(hass, hass_client)
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_album_art_requested_once(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the album art is only requested when the track changes."""
    freezer.move_to("2026-11-25T00:00:00+00:00")
    with patch.object(
        Track, "get_cover_image", autospec=True, return_value=COVER_IMAGE
    ) as mock_cover:
        await setup_integration(config_entry, default_user)
        await _async_update(hass, freezer, default_user)

    assert mock_cover.call_count == 1
    assert hass.states.get(ENTITY_ID).state == "2026-11-25T00:00:00+00:00"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NetworkError("network", OSError()), id="network_error"),
        pytest.param(
            MalformedResponseError("network", ValueError()), id="malformed_response"
        ),
        pytest.param(
            WSError("network", "11", "Service Offline"), id="retryable_api_error"
        ),
    ],
)
async def test_album_art_transient_error_retried(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
    error: PyLastError,
) -> None:
    """Test a failed album art request is retried on the next update only."""
    with patch.object(
        Track, "get_cover_image", autospec=True, side_effect=error
    ) as mock_cover:
        await setup_integration(config_entry, default_user)
        # Both configured users play the same track
        assert mock_cover.call_count == 1
        assert config_entry.runtime_data.data["testaccount1"].now_playing_image is None

        mock_cover.side_effect = None
        mock_cover.return_value = COVER_IMAGE
        await _async_update(hass, freezer, default_user)

    assert mock_cover.call_count == 2
    assert config_entry.runtime_data.data["testaccount1"].now_playing_image == (
        COVER_IMAGE
    )


async def test_album_art_permanent_error_cached(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the album art is not requested again after a permanent error."""
    with patch.object(
        Track,
        "get_cover_image",
        autospec=True,
        side_effect=WSError("network", "6", "Track not found"),
    ) as mock_cover:
        await setup_integration(config_entry, default_user)
        await _async_update(hass, freezer, default_user)

    assert mock_cover.call_count == 1
    assert config_entry.runtime_data.data["testaccount1"].now_playing_image is None
