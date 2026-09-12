"""The request Core sends to the push relay, and what it does with every answer."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.mobile_app.const import DATA_CONFIG_ENTRIES, DOMAIN
from homeassistant.components.mobile_app.remote_media.push import (
    PushOutcome,
    async_send,
    build_request,
)
from homeassistant.core import HomeAssistant

from .const import ENTITY_ID, PUSH_TOKEN, PUSH_URL, SESSION_ID

from tests.test_util.aiohttp import AiohttpClientMocker

ATTRIBUTES: dict[str, Any] = {
    "id": SESSION_ID,
    "generation": "gen-1",
    "snapshot": {
        "selection": {"serverId": "home", "entityId": ENTITY_ID},
        "deviceName": "Speaker",
        "state": "playing",
        "features": 84037,
    },
}


async def test_the_request_body_is_the_relay_contract(
    hass: HomeAssistant, push_entry
) -> None:
    """Exactly the fields `functions/now-playing.js` validates, and nothing more."""
    body = build_request(push_entry, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES)

    assert body == {
        # Still the ordinary Companion token: the relay's registration and metering identity.
        "push_token": "COMPANION_TOKEN",
        # The specialised APNs destination. Never a substitute for the one above.
        "now_playing_token": PUSH_TOKEN,
        "now_playing": {
            "event": "update",
            "timestamp": 1788749001,
            "attributes": ATTRIBUTES,
        },
        "registration_info": {
            "app_id": "io.robbie.HomeAssistant",
            "app_version": "2026.9.1",
            "webhook_id": push_entry.data["webhook_id"],
            "os_version": "27.0",
        },
    }


async def test_core_chooses_nothing_about_apns(hass: HomeAssistant, push_entry) -> None:
    """The relay owns the topic, the host and the provider. Core must not name any of them."""
    body = build_request(push_entry, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES)
    encoded = repr(body)
    for forbidden in (
        "topic",
        "apns_topic",
        "push-type",
        "api.push.apple.com",
        "api.sandbox.push.apple.com",
        "production",
        "sandbox",
        "aps-environment",
        "key_id",
        "team_id",
    ):
        assert forbidden not in encoded, forbidden


async def test_a_201_is_delivered(
    hass: HomeAssistant, push_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """The relay's success shape."""
    aioclient_mock.post(
        PUSH_URL,
        status=HTTPStatus.CREATED,
        json={"messageId": "APNS-1", "delivery": "nowplaying", "target": "abc"},
    )
    result = await async_send(
        hass, push_entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
    )
    assert result.outcome is PushOutcome.DELIVERED


@pytest.mark.parametrize(
    ("status", "error_type", "outcome"),
    [
        # The only answer that means the user's session token is dead.
        (HTTPStatus.GONE, "InvalidToken", PushOutcome.REMOVE),
        # Relay deployment and credential faults. Never the token's fault.
        (HTTPStatus.FORBIDDEN, "UnsupportedApp", PushOutcome.MISCONFIGURED),
        (HTTPStatus.BAD_REQUEST, "TopicMismatch", PushOutcome.MISCONFIGURED),
        (HTTPStatus.BAD_GATEWAY, "ProviderAuth", PushOutcome.MISCONFIGURED),
        (
            HTTPStatus.NOT_IMPLEMENTED,
            "NowPlayingNotConfigured",
            PushOutcome.MISCONFIGURED,
        ),
        # Our own request being wrong is a bug here, not a reason to unregister.
        (HTTPStatus.BAD_REQUEST, "AmbiguousRequest", PushOutcome.MISCONFIGURED),
        (HTTPStatus.BAD_REQUEST, "InvalidNowPlayingToken", PushOutcome.MISCONFIGURED),
        (HTTPStatus.BAD_REQUEST, "InvalidNowPlayingRequest", PushOutcome.MISCONFIGURED),
        (
            HTTPStatus.BAD_REQUEST,
            "UnsupportedNowPlayingEvent",
            PushOutcome.MISCONFIGURED,
        ),
        (
            HTTPStatus.BAD_REQUEST,
            "InvalidNowPlayingTimestamp",
            PushOutcome.MISCONFIGURED,
        ),
        (
            HTTPStatus.BAD_REQUEST,
            "InvalidNowPlayingAttributes",
            PushOutcome.MISCONFIGURED,
        ),
        (
            HTTPStatus.BAD_REQUEST,
            "MissingNowPlayingSessionId",
            PushOutcome.MISCONFIGURED,
        ),
        (
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "PayloadTooLarge",
            PushOutcome.MISCONFIGURED,
        ),
        # Told to slow down.
        (HTTPStatus.TOO_MANY_REQUESTS, "RateLimited", PushOutcome.BACK_OFF),
        (HTTPStatus.TOO_MANY_REQUESTS, "ApnsRateLimited", PushOutcome.BACK_OFF),
        # Transient.
        (HTTPStatus.BAD_GATEWAY, "ApnsUnavailable", PushOutcome.RETRY),
        # Something the relay grew after this was written.
        (HTTPStatus.BAD_REQUEST, "SomethingNewFromTheRelay", PushOutcome.MISCONFIGURED),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "ApnsError", PushOutcome.RETRY),
    ],
)
async def test_every_relay_error_type_is_classified(
    hass: HomeAssistant,
    push_entry,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error_type: str,
    outcome: PushOutcome,
) -> None:
    """The whole committed error contract, mapped to what Core does about it."""
    aioclient_mock.post(PUSH_URL, status=status, json={"errorType": error_type})
    result = await async_send(
        hass, push_entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
    )
    assert result.outcome is outcome
    assert result.error_type == error_type


async def test_only_an_invalid_token_unregisters(
    hass: HomeAssistant, push_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """The invariant worth stating on its own.

    Deleting a registration over a topic or credential fault would silently stop a feature the
    user never turned off, and it would come back only if they noticed and re-followed.
    """
    for error_type in (
        "UnsupportedApp",
        "TopicMismatch",
        "ProviderAuth",
        "NowPlayingNotConfigured",
        "PayloadTooLarge",
        "RateLimited",
        "ApnsRateLimited",
        "ApnsUnavailable",
        "ApnsError",
        "Unrecognised",
    ):
        aioclient_mock.clear_requests()
        aioclient_mock.post(
            PUSH_URL, status=HTTPStatus.BAD_REQUEST, json={"errorType": error_type}
        )
        result = await async_send(
            hass, push_entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
        )
        assert result.outcome is not PushOutcome.REMOVE, error_type


@pytest.mark.parametrize(
    ("exc", "error_type"),
    [
        (TimeoutError(), "Timeout"),
        (ClientConnectionError("no route to host"), "Unreachable"),
    ],
    ids=["timeout", "connection refused"],
)
async def test_an_unreachable_relay_is_retryable(
    hass: HomeAssistant,
    push_entry,
    aioclient_mock: AiohttpClientMocker,
    exc: Exception,
    error_type: str,
) -> None:
    """A relay outage must not cost anyone their session."""
    aioclient_mock.post(PUSH_URL, exc=exc)
    result = await async_send(
        hass, push_entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
    )
    assert result.outcome is PushOutcome.RETRY
    assert result.error_type == error_type


async def test_a_response_that_is_not_json_is_not_fatal(
    hass: HomeAssistant, push_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A proxy error page is still an answer."""
    aioclient_mock.post(
        PUSH_URL, status=HTTPStatus.BAD_GATEWAY, text="<html>gateway</html>"
    )
    result = await async_send(
        hass, push_entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
    )
    assert result.outcome is PushOutcome.RETRY


async def test_a_registration_without_cloud_push_sends_nothing(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Local-push-only registrations have nowhere to send, and should not be retried at."""
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][
        create_registrations[1]["webhook_id"]
    ]
    result = await async_send(
        hass, entry, SESSION_ID, PUSH_TOKEN, "update", 1788749001, ATTRIBUTES
    )
    assert result.outcome is PushOutcome.MISCONFIGURED
    assert aioclient_mock.call_count == 0


async def test_an_end_event_carries_only_the_identity(
    hass: HomeAssistant, push_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Ending needs the session identity; the app may already have torn the session down."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await async_send(
        hass, push_entry, SESSION_ID, PUSH_TOKEN, "end", 1788749002, {"id": SESSION_ID}
    )
    sent = aioclient_mock.mock_calls[0][2]
    assert sent["now_playing"] == {
        "event": "end",
        "timestamp": 1788749002,
        "attributes": {"id": SESSION_ID},
    }
