"""The two webhook commands the iOS app calls to start and stop following a player."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.mobile_app.const import DATA_CONFIG_ENTRIES, DOMAIN
from homeassistant.components.mobile_app.remote_media.const import COALESCE_SECONDS
from homeassistant.components.mobile_app.remote_media.manager import async_get_manager
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import STORED_SNAPSHOT, stored_sessions
from .const import (
    ENTITY_ID,
    GENERATION,
    LATER_GENERATION,
    LATER_PUSH_TOKEN,
    LATER_SEQUENCE,
    PLAYING_ATTRIBUTES,
    PUSH_TOKEN,
    PUSH_URL,
    SEQUENCE,
    SERVER_ID,
    SESSION_ID,
    dismissal_payload,
    registration_payload,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def _post(
    client: TestClient, webhook_id: str, webhook_type: str, data: dict[str, Any]
):
    """Send one webhook command."""
    return await client.post(
        f"/api/webhook/{webhook_id}", json={"type": webhook_type, "data": data}
    )


async def _register(client: TestClient, webhook_id: str, **overrides):
    """Register a Follow relationship."""
    return await _post(
        client,
        webhook_id,
        "remote_media_session_token",
        registration_payload(**overrides),
    )


@pytest.fixture
async def registration(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
) -> str:
    """A push-capable registration webhook id, with the followed player present.

    The shared `create_registrations` fixture makes registrations whose `app_data` is a placeholder
    with no push configuration, and a relationship for one of those is stored without being
    watched. Following needs a registration Core can actually reach.
    """
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    webhook_id = create_registrations[1]["webhook_id"]
    # pylint: disable-next=home-assistant-use-runtime-data
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "app_data": {"push_token": "COMPANION_TOKEN", "push_url": PUSH_URL},
        },
    )
    await hass.async_block_till_done()
    return webhook_id


@pytest.fixture
async def local_only_registration(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
) -> str:
    """A registration with no cloud push configuration, exactly as created."""
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    await hass.async_block_till_done()
    return create_registrations[1]["webhook_id"]


async def test_registration_is_stored_under_the_requesting_webhook(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A session belongs to the authenticated registration that sent it, not to the payload."""
    resp = await _register(webhook_client, registration)
    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}

    stored = stored_sessions(hass, registration)
    assert set(stored) == {SESSION_ID}
    assert stored[SESSION_ID] == {
        "session_id": SESSION_ID,
        "generation": GENERATION,
        "generation_sequence": SEQUENCE,
        "entity_id": ENTITY_ID,
        "server_id": SERVER_ID,
        "push_token": PUSH_TOKEN,
        "schema_version": 1,
        "last_timestamp": None,
        "last_snapshot": None,
    }


async def test_registration_starts_watching_the_player(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """The listener attaches immediately, so the card can be brought up to date."""
    await _register(webhook_client, registration)
    manager = async_get_manager(hass)
    assert manager.async_get(registration, SESSION_ID) is not None
    assert ENTITY_ID in manager.watchers


async def test_only_media_players_may_be_followed(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A registration must not become a subscription to arbitrary state."""
    resp = await _register(webhook_client, registration, entity_id="light.kitchen")
    # mobile_app answers a refused payload with 200 and ignores it.
    assert resp.status == HTTPStatus.OK
    assert stored_sessions(hass, registration) == {}


@pytest.mark.parametrize(
    "overrides",
    [
        {"push_token": "not-hex"},
        {"push_token": "abc"},
        {"push_token": ""},
        {"push_token": "ab" * 400},
        {"schema_version": 2},
        {"schema_version": 0},
        {"session_id": ""},
        {"generation": ""},
        {"generation": "g" * 300},
        {"entity_id": "not_an_entity"},
        {"server_id": ""},
        {"server_id": "s" * 300},
        {"generation_sequence": 0},
        {"generation_sequence": -1},
        {"generation_sequence": "ten"},
        {"generation_sequence": 9_007_199_254_740_992},
    ],
)
async def test_malformed_registrations_are_refused(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    overrides: dict[str, Any],
) -> None:
    """Validation is shallow but not absent. Refusals answer 200 and store nothing."""
    resp = await _register(webhook_client, registration, **overrides)
    assert resp.status == HTTPStatus.OK
    assert stored_sessions(hass, registration) == {}


@pytest.mark.parametrize(
    "session_id",
    [
        "4:homemedia_player.other",
        "not-the-app-construction",
        "a",
        "{}",
        "session/with/slashes",
        "1:2:3",
    ],
)
async def test_the_session_identifier_is_opaque(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    session_id: str,
) -> None:
    """Apple's identifier, stored byte-for-byte and never parsed.

    Core used to recover the app's server id from its shape, which coupled a Home Assistant
    release to a private detail of the app. The app states the server explicitly instead, so any
    non-empty identifier is acceptable and is echoed back exactly as it arrived.
    """
    resp = await _register(webhook_client, registration, session_id=session_id)
    assert resp.status == HTTPStatus.OK

    stored = stored_sessions(hass, registration)
    assert set(stored) == {session_id}
    assert stored[session_id]["session_id"] == session_id
    # And the server the relationship is about came from the payload, not from the identifier.
    assert stored[session_id]["server_id"] == SERVER_ID


async def test_the_server_id_is_taken_from_the_payload(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Whatever the app calls its server is what the snapshot's selection has to carry."""
    await _register(
        webhook_client,
        registration,
        server_id="66ecff02b21c4c788b60f11169fd7c81",
        session_id="an-identifier-that-encodes-nothing",
    )
    stored = stored_sessions(hass, registration)["an-identifier-that-encodes-nothing"]
    assert stored["server_id"] == "66ecff02b21c4c788b60f11169fd7c81"
    publisher = async_get_manager(hass).async_get(
        registration, "an-identifier-that-encodes-nothing"
    )
    assert publisher.session.server_id == "66ecff02b21c4c788b60f11169fd7c81"


async def test_a_missing_entity_does_not_prevent_registration(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """The player may not exist yet — an integration can load after the phone registers."""
    hass.states.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    resp = await _register(webhook_client, registration)
    assert resp.status == HTTPStatus.OK
    assert SESSION_ID in stored_sessions(hass, registration)
    # Watching anyway, so the card starts as soon as the player appears.
    assert ENTITY_ID in async_get_manager(hass).watchers


@pytest.mark.parametrize("state", ["paused", "idle", "off", "unavailable", "unknown"])
async def test_a_player_that_is_not_playing_can_still_be_followed(
    hass: HomeAssistant, registration: str, webhook_client: TestClient, state: str
) -> None:
    """Following is a user relationship, not a playback state."""
    hass.states.async_set(ENTITY_ID, state, {"friendly_name": "Speaker"})
    resp = await _register(webhook_client, registration)
    assert resp.status == HTTPStatus.OK
    assert SESSION_ID in stored_sessions(hass, registration)


async def test_an_identical_registration_is_idempotent(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """The app re-registers the same token; that must not double anything up."""
    await _register(webhook_client, registration)
    first = async_get_manager(hass).async_get(registration, SESSION_ID)
    await _register(webhook_client, registration)
    assert async_get_manager(hass).async_get(registration, SESSION_ID) is first
    assert len(stored_sessions(hass, registration)) == 1
    assert len(async_get_manager(hass).watchers[ENTITY_ID].publishers) == 1


async def test_a_replacement_token_supersedes_the_old_one(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Same Follow lifetime, new token: the new one becomes the only destination."""
    await _register(webhook_client, registration)
    replacement = "41" + "cd" * 79
    await _register(webhook_client, registration, push_token=replacement)

    stored = stored_sessions(hass, registration)[SESSION_ID]
    assert stored["push_token"] == replacement
    assert stored["generation"] == GENERATION
    publisher = async_get_manager(hass).async_get(registration, SESSION_ID)
    assert publisher.session.push_token == replacement


async def test_a_replacement_token_keeps_the_lifetimes_state(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A token rotation is the same card, so its sticky state and clock survive."""
    await _register(webhook_client, registration)
    seeded = stored_sessions(hass, registration)[SESSION_ID]
    seeded["last_timestamp"] = 4242
    seeded["last_snapshot"] = STORED_SNAPSHOT

    await _register(webhook_client, registration, push_token=LATER_PUSH_TOKEN)
    stored = stored_sessions(hass, registration)[SESSION_ID]
    assert stored["push_token"] == LATER_PUSH_TOKEN
    assert stored["last_timestamp"] == 4242
    assert stored["last_snapshot"] == STORED_SNAPSHOT


async def test_a_later_follow_replaces_the_previous_one(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Following again after stopping is a later relationship, and it wins."""
    await _register(webhook_client, registration)
    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
    )

    stored = stored_sessions(hass, registration)
    assert len(stored) == 1
    assert stored[SESSION_ID]["generation"] == LATER_GENERATION
    assert stored[SESSION_ID]["generation_sequence"] == LATER_SEQUENCE
    # Still exactly one listener for the player.
    assert len(async_get_manager(hass).watchers[ENTITY_ID].publishers) == 1


async def test_a_later_follow_starts_from_a_clean_slate(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A new relationship is a new APNs session, so it inherits nothing from the last.

    The track the old card was showing and the ordering clock the old session was sequenced by
    both belong to a session that has ended. Carrying either would mean the first push of the new
    relationship describes the old one, or is dropped as out of order.
    """
    await _register(webhook_client, registration)
    seeded = stored_sessions(hass, registration)[SESSION_ID]
    seeded["last_timestamp"] = 999_999
    seeded["last_snapshot"] = STORED_SNAPSHOT

    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
        push_token=LATER_PUSH_TOKEN,
    )

    stored = stored_sessions(hass, registration)[SESSION_ID]
    assert stored["last_timestamp"] is None
    assert stored["last_snapshot"] is None
    assert stored["push_token"] == LATER_PUSH_TOKEN


async def test_a_late_registration_cannot_overwrite_a_later_follow(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """The race the sequence exists for, end to end.

    Registration happens in an extension process whose lifetime the app does not control, so a
    registration describing a relationship the user has already replaced can arrive after the
    replacement's. Nothing about the stale one may be applied: not the token, not the entity, not
    the sticky state, not the clock, and no listener may move.
    """
    # Follow A, then stop and follow again as B.
    await _register(webhook_client, registration)
    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
        push_token=LATER_PUSH_TOKEN,
    )
    publisher = async_get_manager(hass).async_get(registration, SESSION_ID)

    # A's registration finally lands.
    resp = await _register(webhook_client, registration)
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    stored = stored_sessions(hass, registration)[SESSION_ID]
    assert stored["generation"] == LATER_GENERATION
    assert stored["generation_sequence"] == LATER_SEQUENCE
    assert stored["push_token"] == LATER_PUSH_TOKEN
    # And the publisher B was using was left exactly where it was.
    assert async_get_manager(hass).async_get(registration, SESSION_ID) is publisher
    assert len(async_get_manager(hass).watchers[ENTITY_ID].publishers) == 1


async def test_a_late_registration_cannot_move_the_followed_entity(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A stale registration naming another player must not move the listener either."""
    hass.states.async_set("media_player.other", "playing", PLAYING_ATTRIBUTES)
    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
    )
    await _register(webhook_client, registration, entity_id="media_player.other")
    await hass.async_block_till_done()

    assert stored_sessions(hass, registration)[SESSION_ID]["entity_id"] == ENTITY_ID
    assert "media_player.other" not in async_get_manager(hass).watchers


async def test_one_sequence_claimed_by_two_relationships_is_refused(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A conflict, not a race to resolve.

    The app increments its counter once per relationship, so two different generations at the same
    sequence cannot both be right — and guessing which is newer would be exactly the heuristic the
    sequence exists to remove.
    """
    await _register(webhook_client, registration)
    resp = await _register(webhook_client, registration, generation=LATER_GENERATION)
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    stored = stored_sessions(hass, registration)[SESSION_ID]
    assert stored["generation"] == GENERATION
    assert stored["push_token"] == PUSH_TOKEN


async def test_a_session_stored_without_a_sequence_accepts_an_ordered_one(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Upgrading a development install, where a stored session predates ordering.

    Nothing released ever wrote one, so this only has to be survivable: an unordered stored
    session cannot be compared with anything, and the first ordered registration takes over.
    """
    await _register(webhook_client, registration)
    stored = stored_sessions(hass, registration)
    stored[SESSION_ID]["generation_sequence"] = None

    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
    )
    assert stored_sessions(hass, registration)[SESSION_ID]["generation_sequence"] == (
        LATER_SEQUENCE
    )


async def test_a_registration_without_push_is_stored_but_not_watched(
    hass: HomeAssistant, local_only_registration: str, webhook_client: TestClient
) -> None:
    """Core cannot reach it, so watching would shape traffic for requests that cannot be sent.

    The relationship is still remembered: the phone has asked to follow, and deleting it because
    push is not configured yet would mean the user has to notice and re-follow.
    """
    resp = await _register(webhook_client, local_only_registration)
    assert resp.status == HTTPStatus.OK

    assert SESSION_ID in stored_sessions(hass, local_only_registration)
    manager = async_get_manager(hass)
    assert manager.async_get(local_only_registration, SESSION_ID) is None
    assert ENTITY_ID not in manager.watchers
    assert manager.async_is_known(local_only_registration, SESSION_ID)


async def test_gaining_push_starts_watching_a_stored_relationship(
    hass: HomeAssistant,
    local_only_registration: str,
    webhook_client: TestClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`update_registration` is the lifecycle point where push arrives."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await _register(webhook_client, local_only_registration)
    # pylint: disable-next=home-assistant-use-runtime-data
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][local_only_registration]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "app_data": {"push_token": "COMPANION_TOKEN", "push_url": PUSH_URL},
        },
    )
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + dt_util.dt.timedelta(seconds=COALESCE_SECONDS + 0.1)
    )
    await hass.async_block_till_done()

    manager = async_get_manager(hass)
    assert manager.async_get(local_only_registration, SESSION_ID) is not None
    assert ENTITY_ID in manager.watchers
    # And the card is brought up to date, rather than waiting for the player to change.
    assert aioclient_mock.mock_calls


async def test_losing_push_stops_watching_but_keeps_the_relationship(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """A temporary push loss makes the follow dormant instead of retrying forever."""
    await _register(webhook_client, registration)
    manager = async_get_manager(hass)
    assert manager.async_get(registration, SESSION_ID) is not None

    # pylint: disable-next=home-assistant-use-runtime-data
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][registration]
    hass.config_entries.async_update_entry(entry, data={**entry.data, "app_data": {}})
    await hass.async_block_till_done()

    assert manager.async_get(registration, SESSION_ID) is None
    assert ENTITY_ID not in manager.watchers
    assert manager.async_is_known(registration, SESSION_ID)
    assert SESSION_ID in stored_sessions(hass, registration)


async def test_a_matching_dismissal_stops_following(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Stop Following removes the relationship."""
    await _register(webhook_client, registration)
    resp = await _post(
        webhook_client,
        registration,
        "remote_media_session_dismissed",
        dismissal_payload(),
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    assert stored_sessions(hass, registration) == {}
    assert async_get_manager(hass).async_get(registration, SESSION_ID) is None
    # The last session for the player took its listener with it.
    assert ENTITY_ID not in async_get_manager(hass).watchers


async def test_a_late_dismissal_cannot_remove_a_later_follow(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """The other half of the race, end to end.

    The app writes down a dismissal it could not send and retries it on a later launch, so one can
    arrive long after the user has followed again. Both halves of the relationship have to match
    the stored one: the sequence says it is older, and there is nothing to guess.
    """
    await _register(
        webhook_client,
        registration,
        generation=LATER_GENERATION,
        generation_sequence=LATER_SEQUENCE,
    )
    resp = await _post(
        webhook_client,
        registration,
        "remote_media_session_dismissed",
        dismissal_payload(generation=GENERATION, generation_sequence=SEQUENCE),
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    stored = stored_sessions(hass, registration)
    assert stored[SESSION_ID]["generation"] == LATER_GENERATION
    assert stored[SESSION_ID]["generation_sequence"] == LATER_SEQUENCE
    assert async_get_manager(hass).async_get(registration, SESSION_ID) is not None


@pytest.mark.parametrize(
    "overrides",
    [
        # The right sequence but a different relationship: a conflict, not a match.
        {"generation": LATER_GENERATION},
        # The right relationship at the wrong place in the order.
        {"generation_sequence": LATER_SEQUENCE},
        {"generation_sequence": 1},
    ],
)
async def test_a_dismissal_must_name_the_stored_relationship_exactly(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    overrides: dict[str, Any],
) -> None:
    """Half a match is no match. Removing on one would reopen the race."""
    await _register(webhook_client, registration)
    resp = await _post(
        webhook_client,
        registration,
        "remote_media_session_dismissed",
        dismissal_payload(**overrides),
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    assert SESSION_ID in stored_sessions(hass, registration)


@pytest.mark.parametrize(
    "overrides",
    [
        {"generation": ""},
        {"generation_sequence": 0},
        {"generation_sequence": -1},
        {"generation_sequence": "ten"},
    ],
)
async def test_malformed_dismissals_are_refused(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    overrides: dict[str, Any],
) -> None:
    """A dismissal that does not describe a relationship cannot end one."""
    await _register(webhook_client, registration)
    resp = await _post(
        webhook_client,
        registration,
        "remote_media_session_dismissed",
        dismissal_payload(**overrides),
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    assert SESSION_ID in stored_sessions(hass, registration)


async def test_a_dismissal_for_an_unknown_session_is_harmless(
    hass: HomeAssistant, registration: str, webhook_client: TestClient
) -> None:
    """Nothing to do, and nothing to complain about."""
    resp = await _post(
        webhook_client,
        registration,
        "remote_media_session_dismissed",
        dismissal_payload(session_id="4:homemedia_player.nothing"),
    )
    assert resp.status == HTTPStatus.OK


async def test_one_registration_cannot_dismiss_another(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Sessions are owned by the config entry that registered them."""
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    owner = create_registrations[1]["webhook_id"]
    other = create_registrations[0]["webhook_id"]
    await _register(webhook_client, owner)

    await _post(
        webhook_client, other, "remote_media_session_dismissed", dismissal_payload()
    )
    await hass.async_block_till_done()
    assert SESSION_ID in stored_sessions(hass, owner)


async def test_the_session_token_never_reaches_the_log(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`mobile_app` logs every decrypted payload at debug level.

    That is right for the other commands and wrong for this one: the token is a live APNs
    destination for the user's device.
    """
    with caplog.at_level(logging.DEBUG):
        await _register(webhook_client, registration)
        await hass.async_block_till_done()

    assert PUSH_TOKEN not in caplog.text
    assert "**REDACTED" in caplog.text
    # The rest of the payload is still there to diagnose with.
    assert SESSION_ID in caplog.text
    assert ENTITY_ID in caplog.text


@pytest.mark.parametrize(
    "bad_token",
    ["not-hex-at-all", "abc", "ab" * 400, 12345, None, {"nested": "value"}],
)
async def test_a_refused_token_is_not_echoed_into_the_log(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    caplog: pytest.LogCaptureFixture,
    bad_token: Any,
) -> None:
    """A rejected token must not be more exposed than an accepted one.

    `validate_schema` reports failures with `humanize_error`, which echoes the offending value at
    ERROR level — on by default. So the token is validated in the handler instead.
    """
    with caplog.at_level(logging.DEBUG):
        resp = await _register(webhook_client, registration, push_token=bad_token)
        await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    assert stored_sessions(hass, registration) == {}
    if isinstance(bad_token, str) and len(bad_token) > 8:
        assert bad_token not in caplog.text


async def test_other_webhook_payloads_are_logged_unchanged(
    hass: HomeAssistant,
    registration: str,
    webhook_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The redaction is per command, not a blanket change to webhook logging."""
    with caplog.at_level(logging.DEBUG):
        await _post(
            webhook_client,
            registration,
            "fire_event",
            {"event_type": "test_event", "event_data": {"hello": "yo world"}},
        )
        await hass.async_block_till_done()
    assert "yo world" in caplog.text
    assert "**REDACTED" not in caplog.text
