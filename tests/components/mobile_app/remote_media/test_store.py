"""Persistence: a Follow relationship must survive a restart without the phone re-registering."""

from typing import Any

import pytest

from homeassistant.components.mobile_app.const import (
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_REMOTE_MEDIA_SESSIONS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_VERSION_MINOR,
)
from homeassistant.components.mobile_app.remote_media.manager import async_get_manager
from homeassistant.components.mobile_app.remote_media.model import (
    RemoteMediaSession,
    RemoteMediaSnapshot,
)
from homeassistant.components.mobile_app.remote_media.store import async_load_sessions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import WEBHOOK_ID, stored_session
from .const import ENTITY_ID, PLAYING_ATTRIBUTES, PUSH_TOKEN, SESSION_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


def test_a_session_round_trips_through_storage() -> None:
    """Everything needed to resume, and nothing that is not JSON."""
    data = stored_session()
    session = RemoteMediaSession.from_storage(data)
    assert session is not None
    assert session.as_storage() == data

    # Only JSON-safe values: the store serializes dictionaries.
    def assert_json_safe(value: Any) -> None:
        assert value is None or isinstance(value, (str, int, float, bool, dict, list))
        if isinstance(value, dict):
            for key, item in value.items():
                assert isinstance(key, str)
                assert_json_safe(item)

    assert_json_safe(session.as_storage())


def test_the_companion_token_is_not_copied_into_the_store() -> None:
    """It lives on the config entry; a second copy would be a second thing to leak."""
    keys = set(stored_session())
    assert "app_data" not in keys
    assert keys == {
        "session_id",
        "generation",
        "generation_sequence",
        "entity_id",
        "server_id",
        "push_token",
        "schema_version",
        "last_timestamp",
        "last_snapshot",
    }


@pytest.mark.parametrize(
    "broken",
    [
        {"session_id": None},
        {"generation": None},
        {"entity_id": None},
        {"schema_version": None},
        {"push_token": None},
    ],
)
def test_an_unreadable_session_is_discarded_not_raised(broken: dict[str, Any]) -> None:
    """One malformed entry must not stop a registration from loading."""
    data = stored_session()
    for key in broken:
        del data[key]
    assert RemoteMediaSession.from_storage(data) is None


async def test_an_unreadable_stored_session_does_not_stop_the_others(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The store is shared with the rest of `mobile_app`, so one bad row cannot break loading."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID] = {
        "broken": {"session_id": "broken"},
        SESSION_ID: stored_session(),
    }

    loaded = async_load_sessions(hass, WEBHOOK_ID)

    assert [session.session_id for session in loaded] == [SESSION_ID]
    assert "Discarding unreadable Remote Now Playing session broken" in caplog.text


def test_a_session_without_sticky_state_loads() -> None:
    """A relationship registered but never yet pushed."""
    session = RemoteMediaSession.from_storage(
        stored_session(last_timestamp=None, last_snapshot=None)
    )
    assert session is not None
    assert session.last_snapshot is None


def test_an_unreadable_snapshot_does_not_lose_the_session() -> None:
    """Losing sticky state is recoverable; losing the token is not."""
    session = RemoteMediaSession.from_storage(
        stored_session(last_snapshot={"bogus": 1})
    )
    assert session is not None
    assert session.last_snapshot is None
    assert session.push_token == PUSH_TOKEN


async def test_migration_from_the_previous_minor_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An existing installation gains empty Remote Now Playing storage.

    Live Activity data has to come through untouched: this is the same store.
    """
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "data": {
            "deleted_ids": ["gone"],
            DATA_LIVE_ACTIVITY_TOKENS: {
                "webhook-1": {"washer": {"token": "abc", "expires_at": 1e12}}
            },
        },
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data[DOMAIN]
    assert domain_data[DATA_REMOTE_MEDIA_SESSIONS] == {}
    assert domain_data[DATA_LIVE_ACTIVITY_TOKENS] == {
        "webhook-1": {"washer": {"token": "abc", "expires_at": 1e12}}
    }
    assert domain_data["deleted_ids"] == ["gone"]


async def test_a_fresh_installation_starts_empty(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """No stored data at all."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    # pylint: disable-next=home-assistant-use-runtime-data
    assert hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS] == {}


async def test_sessions_are_restored_when_their_registration_loads(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A restart resumes following, with its sticky state and its ordering clock."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_VERSION_MINOR,
        "data": {
            "deleted_ids": [],
            DATA_LIVE_ACTIVITY_TOKENS: {},
            DATA_REMOTE_MEDIA_SESSIONS: {WEBHOOK_ID: {SESSION_ID: stored_session()}},
        },
    }
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)

    entry = MockConfigEntry(
        data={
            "app_data": {"push_token": "COMPANION_TOKEN", "push_url": "http://x/push"},
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2026.9.1",
            "device_id": "device-1",
            "device_name": "Test iPhone",
            "manufacturer": "Apple",
            "model": "iPhone",
            "os_name": "iOS",
            "os_version": "27.0",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": "user-1",
            "webhook_id": WEBHOOK_ID,
        },
        domain=DOMAIN,
        source="registration",
        title="Test iPhone",
        version=1,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    manager = async_get_manager(hass)
    publisher = manager.async_get(WEBHOOK_ID, SESSION_ID)
    assert publisher is not None
    # The listener is back, without the phone doing anything.
    assert ENTITY_ID in manager.watchers
    # And so is the state that stops a restart re-pushing what the card already shows.
    assert publisher.session.last_timestamp == 1788739200
    assert publisher.session.last_snapshot is not None
    assert publisher.session.last_snapshot.title == "First"


async def test_removing_a_registration_clears_its_sessions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Deleting the mobile_app entry takes its Follow relationships with it."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_VERSION_MINOR,
        "data": {
            "deleted_ids": [],
            DATA_LIVE_ACTIVITY_TOKENS: {},
            DATA_REMOTE_MEDIA_SESSIONS: {WEBHOOK_ID: {SESSION_ID: stored_session()}},
        },
    }
    entry = MockConfigEntry(
        data={
            "app_data": {},
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2026.9.1",
            "device_id": "device-1",
            "device_name": "Test iPhone",
            "manufacturer": "Apple",
            "model": "iPhone",
            "os_name": "iOS",
            "os_version": "27.0",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": "user-1",
            "webhook_id": WEBHOOK_ID,
        },
        domain=DOMAIN,
        source="registration",
        title="Test iPhone",
        version=1,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # pylint: disable-next=home-assistant-use-runtime-data
    assert hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS] == {}
    assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is None
    assert async_get_manager(hass).watchers == {}


async def test_nothing_expires_an_active_session(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Apple documents no lifetime for a Remote Now Playing update token.

    Unlike Live Activity tokens, which carry an `expires_at` because ActivityKit caps Dynamic
    Island updates at twelve hours, there is nothing to age out against — so no expiry was
    invented. A session is kept until it is dismissed, superseded, its registration goes, or the
    relay reports the token dead.
    """
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_VERSION_MINOR,
        "data": {
            "deleted_ids": [],
            DATA_LIVE_ACTIVITY_TOKENS: {},
            DATA_REMOTE_MEDIA_SESSIONS: {WEBHOOK_ID: {SESSION_ID: stored_session()}},
        },
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    stored = stored_session()
    assert "expires_at" not in stored
    # pylint: disable-next=home-assistant-use-runtime-data
    assert (
        hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID][SESSION_ID] == stored
    )


def test_a_snapshot_round_trips() -> None:
    """Sticky state has to survive a restart or the card is rebuilt from nothing."""
    data = stored_session()["last_snapshot"]
    snapshot = RemoteMediaSnapshot.from_storage(data)
    assert snapshot is not None
    assert snapshot.as_storage() == data
    assert snapshot.track_id == "7:track-15:First6:Artist5:Album"
