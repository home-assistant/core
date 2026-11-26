"""Tests for the Last.fm image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pylast import Track, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator
import respx

from homeassistant.const import ATTR_ENTITY_PICTURE, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import COVER_IMAGE, USERNAME_1, MockNetwork, MockUser, mock_track
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


async def test_image_kept_while_unavailable(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed update of one user does not reset the image."""
    freezer.move_to("2026-11-25T00:00:00+00:00")
    await setup_integration(config_entry, default_user)

    failing_user = MockUser(
        thrown_error=WSError("network", "status", "Something strange")
    )
    # The other user keeps updating, so the coordinator update succeeds
    with patch(
        "pylast.User",
        side_effect=lambda name, _: (
            failing_user if name == USERNAME_1 else default_user
        ),
    ):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await _async_update(hass, freezer, default_user)
    assert hass.states.get(ENTITY_ID).state == "2026-11-25T00:00:00+00:00"
