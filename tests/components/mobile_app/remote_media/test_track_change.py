"""A track changing on its own must reach the phone without a second state change.

The physical failure this covers: an Echo advances to the next song in a station, Home Assistant's
own state shows the new song immediately, and the Now Playing card keeps the old one until the user
pauses or unpauses. These drive real `state_changed` events through the registered path rather than
calling `is_meaningful_change` directly, because the comparison was never the broken part.
"""

from http import HTTPStatus
import json
from typing import Any

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.mobile_app.const import DATA_CONFIG_ENTRIES, DOMAIN
from homeassistant.components.mobile_app.remote_media.const import COALESCE_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import stored_sessions
from .const import (
    ENTITY_ID,
    PLAYING_ATTRIBUTES,
    PUSH_URL,
    SESSION_ID,
    registration_payload,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

# What the Echo reports once the station has moved on: new identity, new metadata, and a position
# that has restarted. Nothing here is a playback-state transition.
NEXT_TRACK = {
    **PLAYING_ATTRIBUTES,
    "media_content_id": "track-2",
    "media_title": "Kids",
    "media_artist": "Current Joys",
    "media_album_name": "A Different Age",
    "media_duration": 213,
    "media_position": 0,
    "media_position_updated_at": "2026-09-07T00:04:00+00:00",
}


async def _register(client: TestClient, webhook_id: str, **overrides):
    return await client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "remote_media_session_token",
            "data": registration_payload(**overrides),
        },
    )


async def _settle(hass: HomeAssistant) -> None:
    """Let the coalescing window elapse and any send finish."""
    async_fire_time_changed(
        hass, dt_util.utcnow() + dt_util.dt.timedelta(seconds=COALESCE_SECONDS + 0.1)
    )
    await hass.async_block_till_done()


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta
) -> None:
    """Move both clocks, in steps, so scheduled retries actually come due.

    `_quiet_until` is wall-clock and the timers are the event loop's, so the frozen clock has to
    move with them. Stepped rather than jumped because a retry schedules the next one from inside
    its own callback.
    """
    remaining = dt_util.dt.timedelta(**delta)
    step = dt_util.dt.timedelta(seconds=30)
    while remaining > dt_util.dt.timedelta(0):
        moved = min(step, remaining)
        remaining -= moved
        freezer.tick(moved)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


def _snapshots(mock: AiohttpClientMocker) -> list[dict[str, Any]]:
    """Every snapshot the relay was asked to deliver."""
    return [
        call[2]["now_playing"]["attributes"]["snapshot"]
        for call in mock.mock_calls
        if "snapshot" in call[2]["now_playing"]["attributes"]
    ]


def _stored_snapshot(hass: HomeAssistant, webhook_id: str) -> dict[str, Any] | None:
    """The persisted `last_snapshot` for the session."""
    stored = stored_sessions(hass, webhook_id).get(SESSION_ID)
    return stored.get("last_snapshot") if stored else None


@pytest.fixture
async def following(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    aioclient_mock: AiohttpClientMocker,
) -> str:
    """A registered Follow whose first card has already been delivered."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    webhook_id = create_registrations[1]["webhook_id"]
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "app_data": {"push_token": "COMPANION_TOKEN", "push_url": PUSH_URL},
        },
    )
    await hass.async_block_till_done()
    await _register(webhook_client, webhook_id)
    await _settle(hass)
    assert _snapshots(aioclient_mock), "the first card should have been delivered"
    aioclient_mock.clear_requests()
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    return webhook_id


async def test_a_station_advancing_reaches_the_phone_on_its_own(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The reported bug: playing -> playing, new song, no other change."""
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)

    sent = _snapshots(aioclient_mock)
    assert sent, "a track change while playing must produce an update"
    assert sent[-1]["title"] == "Kids"
    assert sent[-1]["artist"] == "Current Joys"


async def test_the_persisted_snapshot_follows_the_new_track(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`last_snapshot` is what a restart rebuilds the card from."""
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)

    stored = _stored_snapshot(hass, following)
    assert stored is not None
    assert stored["title"] == "Kids"


async def test_metadata_only_change_with_no_position_movement(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Some integrations rewrite only the metadata, leaving position untouched."""
    hass.states.async_set(
        ENTITY_ID,
        "playing",
        {
            **PLAYING_ATTRIBUTES,
            "media_content_id": "track-2",
            "media_title": "Kids",
            "media_artist": "Current Joys",
        },
    )
    await _settle(hass)

    sent = _snapshots(aioclient_mock)
    assert sent and sent[-1]["title"] == "Kids"


async def test_no_pause_or_play_is_needed_to_flush_it(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The workaround must not be the only thing that works."""
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)
    delivered_without_help = len(_snapshots(aioclient_mock))

    # The user's workaround. It must add nothing, because the change already went out.
    hass.states.async_set(ENTITY_ID, "paused", NEXT_TRACK)
    await _settle(hass)
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)

    assert delivered_without_help >= 1
    assert _snapshots(aioclient_mock)[0]["title"] == "Kids"


async def test_a_station_advancing_through_a_transient_gap(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An Echo passes through a blank report between tracks."""
    hass.states.async_set(ENTITY_ID, "playing", {"friendly_name": "Speaker"})
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)

    sent = _snapshots(aioclient_mock)
    assert sent and sent[-1]["title"] == "Kids"


async def test_a_second_advance_still_reaches_the_phone(
    hass: HomeAssistant,
    following: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Whatever unsticks the first must not be a one-off."""
    hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
    await _settle(hass)
    hass.states.async_set(
        ENTITY_ID,
        "playing",
        {**NEXT_TRACK, "media_content_id": "track-3", "media_title": "Third"},
    )
    await _settle(hass)

    assert [snapshot["title"] for snapshot in _snapshots(aioclient_mock)] == [
        "Kids",
        "Third",
    ]


class TestASendThatDidNotLand:
    """What happens to the track the phone never got.

    Alexa-style integrations emit a state event when something changes and not otherwise, so
    "the next state change will re-queue it" can mean "when the user next touches the speaker".
    A track change that fails to send has to be retried on its own.
    """

    async def test_a_relay_error_does_not_lose_the_track(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """The relay was briefly misconfigured; the song that changed during it is still owed."""
        aioclient_mock.clear_requests()
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR, json={})
        hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
        await _settle(hass)
        assert _snapshots(aioclient_mock), "it should at least have tried"

        # The relay is healthy again. No further state event arrives, because nothing about the
        # speaker changed -- it is still playing the same new song.
        aioclient_mock.clear_requests()
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        await _advance(hass, freezer, minutes=5)

        sent = _snapshots(aioclient_mock)
        assert sent, "the track change must be retried without another state event"
        assert sent[-1]["title"] == "Kids"

    async def test_a_rate_limited_send_is_resumed_after_the_backoff(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Being told to slow down must not mean losing what was owed."""
        aioclient_mock.clear_requests()
        aioclient_mock.post(
            PUSH_URL,
            status=HTTPStatus.TOO_MANY_REQUESTS,
            json={"errorType": "RateLimited"},
        )
        hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
        await _settle(hass)

        aioclient_mock.clear_requests()
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        await _advance(hass, freezer, hours=1)

        sent = _snapshots(aioclient_mock)
        assert sent, "the quiet period ending must flush what was waiting"
        assert sent[-1]["title"] == "Kids"

    async def test_a_track_change_during_a_quiet_period_is_not_dropped(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """The song changed while Core was told to stay quiet. It is still the current song."""
        aioclient_mock.clear_requests()
        aioclient_mock.post(
            PUSH_URL,
            status=HTTPStatus.TOO_MANY_REQUESTS,
            json={"errorType": "RateLimited"},
        )
        # First failure opens the quiet period.
        hass.states.async_set(
            ENTITY_ID, "playing", {**NEXT_TRACK, "media_title": "Filler"}
        )
        await _settle(hass)

        # The real track change lands inside the quiet period and no further event follows.
        hass.states.async_set(ENTITY_ID, "playing", NEXT_TRACK)
        await _settle(hass)

        aioclient_mock.clear_requests()
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        await _advance(hass, freezer, hours=1)

        sent = _snapshots(aioclient_mock)
        assert sent, "the newest state must survive the quiet period"
        assert sent[-1]["title"] == "Kids"


class TestArtworkOverTheWire:
    """A cold push has to carry a source, because there is no host app to have prepared one."""

    async def test_a_public_cover_reaches_the_phone(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The Echo case: album art on the service's own CDN."""
        cover = "https://is1-ssl.mzstatic.com/image/thumb/abc/600x600bb.jpg"
        hass.states.async_set(
            ENTITY_ID, "playing", {**NEXT_TRACK, "entity_picture": cover}
        )
        await _settle(hass)

        sent = _snapshots(aioclient_mock)
        assert sent and sent[-1]["artwork"] == {"url": cover}

    async def test_a_signed_proxy_source_is_never_sent(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The relay echoes attributes back, so a token here is a token given away."""
        hass.states.async_set(
            ENTITY_ID,
            "playing",
            {
                **NEXT_TRACK,
                "entity_picture": "/api/media_player_proxy/media_player.speaker?token=secret",
            },
        )
        await _settle(hass)

        sent = _snapshots(aioclient_mock)
        assert sent
        assert "artwork" not in sent[-1]
        # The whole request, not just the snapshot: the signed value must appear nowhere in it.
        # `push_token` and `now_playing_token` are the destination and are expected.
        body = str(aioclient_mock.mock_calls[-1][2])
        assert "secret" not in body
        assert "media_player_proxy" not in body

    async def test_a_new_track_changes_the_artwork_identity(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Or the phone keeps showing the previous song's cover over this song's title."""
        first = "https://cdn.example.com/first.jpg"
        second = "https://cdn.example.com/second.jpg"
        hass.states.async_set(
            ENTITY_ID, "playing", {**PLAYING_ATTRIBUTES, "entity_picture": first}
        )
        await _settle(hass)
        hass.states.async_set(
            ENTITY_ID, "playing", {**NEXT_TRACK, "entity_picture": second}
        )
        await _settle(hass)

        covers = [snapshot.get("artwork") for snapshot in _snapshots(aioclient_mock)]
        assert {"url": first} in covers
        assert covers[-1] == {"url": second}

    async def test_a_cover_changing_alone_is_worth_sending(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Some integrations report the picture a moment after the metadata."""
        hass.states.async_set(
            ENTITY_ID,
            "playing",
            {**PLAYING_ATTRIBUTES, "entity_picture": "https://cdn.example.com/a.jpg"},
        )
        await _settle(hass)
        aioclient_mock.clear_requests()
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        hass.states.async_set(
            ENTITY_ID,
            "playing",
            {**PLAYING_ATTRIBUTES, "entity_picture": "https://cdn.example.com/b.jpg"},
        )
        await _settle(hass)

        sent = _snapshots(aioclient_mock)
        assert sent and sent[-1]["artwork"] == {"url": "https://cdn.example.com/b.jpg"}

    async def test_the_payload_stays_inside_the_relay_limit(
        self,
        hass: HomeAssistant,
        following: str,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The relay refuses anything over 4096 bytes, and a URL is the longest thing added."""
        hass.states.async_set(
            ENTITY_ID,
            "playing",
            {
                **NEXT_TRACK,
                "media_title": "T" * 200,
                "media_artist": "A" * 200,
                "media_album_name": "B" * 200,
                "entity_picture": "https://cdn.example.com/" + "c" * 400 + ".jpg",
            },
        )
        await _settle(hass)

        body = aioclient_mock.mock_calls[-1][2]["now_playing"]["attributes"]
        assert (
            len(
                json.dumps(
                    {"aps": {"event": "update", "timestamp": 1, "attributes": body}}
                )
            )
            < 4096
        )
