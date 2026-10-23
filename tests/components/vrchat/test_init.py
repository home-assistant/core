"""Test the VRChat integration setup and updates."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Never
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.highlevel import AccountIdMismatch
from vrchatapi.highlevel.types import World
from vrchatapi.websocket import VRChatEvent

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vrchat import async_remove_entry
from homeassistant.components.vrchat.const import DOMAIN, USER_AGENT
from homeassistant.components.vrchat.coordinator import (
    VRChatAccountDataCoordinator,
    VRChatAccountSetupFailed,
)
from homeassistant.components.vrchat.store import (
    InitialCurrentUserData,
    VRChatAuthCookieStore,
)
from homeassistant.config_entries import ConfigEntryAuthFailed, ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
)

CURRENT_USER_ID = "usr_current"
FRIEND_USER_ID = "usr_friend"
NEW_FRIEND_USER_ID = "usr_new_friend"

CURRENT_USER = {
    "id": CURRENT_USER_ID,
    "username": "current_user",
    "displayName": "Current user",
    "bio": "Current user bio",
    "friends": [FRIEND_USER_ID],
    "onlineFriends": [],
    "offlineFriends": [],
    "location": "offline",
    "worldId": "offline",
    "instanceId": "offline",
    "status": "offline",
    "statusDescription": "Current description",
    "userIcon": "https://example.com/current-icon.png",
}
FRIEND_USER = {
    "id": FRIEND_USER_ID,
    "displayName": "Friend user",
    "bio": "Friend user bio",
    "location": "offline",
    "worldId": "offline",
    "instanceId": "offline",
    "status": "active",
    "statusDescription": "Friend description",
    "iconUrl": "https://example.com/friend-avatar.png",
}
NEW_FRIEND_USER = {
    "id": NEW_FRIEND_USER_ID,
    "displayName": "New friend",
    "bio": "New friend bio",
    "location": "offline",
    "worldId": "offline",
    "instanceId": "offline",
    "status": "busy",
    "statusDescription": "New friend description",
}


class MockWebSocket:
    """WebSocket that remains connected until closed."""

    def __init__(self) -> None:
        """Initialize the mock WebSocket."""
        self._closed = asyncio.Event()
        self.on_error = Mock()

    def __aiter__(self) -> MockWebSocket:
        """Iterate over WebSocket events."""
        return self

    async def __anext__(self) -> Never:
        """Wait until the WebSocket is closed."""
        await self._closed.wait()
        raise StopAsyncIteration

    async def close(self) -> None:
        """Close the WebSocket."""
        self._closed.set()


@pytest.fixture(autouse=True)
def clear_vrchat_data() -> None:
    """Clear module-level data retained by the integration."""
    InitialCurrentUserData.clear()
    VRChatAuthCookieStore.clear()


def _entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Return the entity ID associated with a VRChat unique ID."""
    entity_id = entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


def test_account_setup_exception_translation() -> None:
    """Test account exceptions use registered translation keys."""
    entry = MockConfigEntry(domain=DOMAIN, title="current_user")

    exception = VRChatAccountSetupFailed(entry)

    assert exception.translation_domain == DOMAIN
    assert exception.translation_key == "setup_failed"
    assert exception.translation_placeholders == {"config_entry_title": "current_user"}


def test_account_auth_exception_translation() -> None:
    """Test the authentication error uses a registered translation key."""
    exception = ConfigEntryAuthFailed(
        translation_domain=DOMAIN,
        translation_key="auth_failed",
        translation_placeholders={"config_entry_title": "current_user"},
    )

    assert exception.translation_domain == DOMAIN
    assert exception.translation_key == "auth_failed"
    assert exception.translation_placeholders == {"config_entry_title": "current_user"}


async def test_setup_websocket_updates_dynamic_friends_and_unload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup, WebSocket updates, dynamic friends, and unloading."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )
    entry.add_to_hass(hass)
    InitialCurrentUserData[CURRENT_USER_ID] = CURRENT_USER.copy()
    websocket = MockWebSocket()

    with (
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.ws_connect",
            new=AsyncMock(return_value=websocket),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_friends",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_user",
            new=AsyncMock(side_effect=[FRIEND_USER.copy(), NEW_FRIEND_USER.copy()]),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.close",
            new=AsyncMock(side_effect=websocket.close),
        ) as mock_api_close,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        state_entity_id = _entity_id(
            entity_registry, f"state.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
        )
        assert hass.states.get(state_entity_id).state == "offline"
        assert "friends" not in hass.states.get(state_entity_id).attributes
        assert entry.runtime_data.client.current_user_data["friends"] == [
            FRIEND_USER_ID
        ]
        assert (
            hass.states.get(state_entity_id).attributes["entity_picture"]
            == "https://example.com/current-icon.png"
        )
        friend_state_entity_id = _entity_id(
            entity_registry, f"state.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
        )
        assert (
            hass.states.get(friend_state_entity_id).attributes["entity_picture"]
            == "https://example.com/friend-avatar.png"
        )
        current_user_status_entity_id = _entity_id(
            entity_registry, f"status.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
        )
        assert hass.states.get(current_user_status_entity_id).state == "offline"
        status_description_entity_id = _entity_id(
            entity_registry,
            f"statusDescription.{CURRENT_USER_ID}:{FRIEND_USER_ID}",
        )
        assert (
            entity_registry.async_get(status_description_entity_id).translation_key
            == "status_description"
        )
        assert (
            hass.states.get(status_description_entity_id).state == "Friend description"
        )
        status_entity_id = _entity_id(
            entity_registry, f"status.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
        )
        assert hass.states.get(status_entity_id).state == "active"
        assert "entity_picture" not in hass.states.get(status_entity_id).attributes

        coordinator = entry.runtime_data
        assert coordinator.client.api.api_client.user_agent == USER_AGENT
        await coordinator.client.handle_event(
            VRChatEvent(
                "friend-update",
                {
                    "userId": FRIEND_USER_ID,
                    "user": {"status": "unknown", "location": "private"},
                },
            )
        )
        await hass.async_block_till_done()
        assert hass.states.get(status_entity_id).state == STATE_UNKNOWN
        assert hass.states.get(friend_state_entity_id).state == STATE_UNKNOWN

        await coordinator.client.handle_event(
            VRChatEvent(
                "user-update", {"userId": FRIEND_USER_ID, "user": {"status": "ask me"}}
            )
        )
        await hass.async_block_till_done()
        assert hass.states.get(status_entity_id).state == "ask_me"

        await coordinator.client.handle_event(
            VRChatEvent(
                "friend-active",
                {
                    "userId": NEW_FRIEND_USER_ID,
                    "user": NEW_FRIEND_USER,
                    "location": "wrld_test:instance",
                },
            )
        )
        await hass.async_block_till_done()
        assert coordinator.data[NEW_FRIEND_USER_ID].data["location"] == (
            "wrld_test:instance"
        )
        new_friend_status_entity_id = _entity_id(
            entity_registry,
            f"status.{CURRENT_USER_ID}:{NEW_FRIEND_USER_ID}",
        )
        assert hass.states.get(new_friend_status_entity_id).state == "busy"
        new_friend_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{CURRENT_USER_ID}:{NEW_FRIEND_USER_ID}"), entry.entry_id
        )
        assert new_friend_device is not None
        current_user_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{CURRENT_USER_ID}:{CURRENT_USER_ID}"), entry.entry_id
        )
        assert current_user_device is not None
        assert new_friend_device.via_device_id == current_user_device.id

        await coordinator.client.handle_event(
            VRChatEvent("friend-delete", {"userId": NEW_FRIEND_USER_ID})
        )
        await hass.async_block_till_done()
        assert NEW_FRIEND_USER_ID not in coordinator.data
        assert device_registry.async_get(new_friend_device.id) is None

        coordinator.client.current_user_data["friends"] = []
        await coordinator.client.fetch_users()
        assert FRIEND_USER_ID not in coordinator.data

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert websocket._closed.is_set()
    mock_api_close.assert_awaited_once()


async def test_remove_entry_logs_out_and_removes_cookie_store(
    hass: HomeAssistant,
) -> None:
    """Test that removing an entry logs out and removes stored cookies."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )
    cookie_store = VRChatAuthCookieStore.setdefault(
        CURRENT_USER_ID,
        Mock(async_load=AsyncMock(return_value={}), async_remove=AsyncMock()),
    )

    with patch(
        "homeassistant.components.vrchat.VRChatAPI.logout", new=AsyncMock()
    ) as mock_logout:
        await async_remove_entry(hass, entry)

    mock_logout.assert_awaited_once()
    cookie_store.async_remove.assert_awaited_once()
    assert CURRENT_USER_ID not in VRChatAuthCookieStore


async def test_remove_entry_without_cookie_store(hass: HomeAssistant) -> None:
    """Test removing an entry when its cookie store was already removed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )

    async def remove_cookie_store() -> None:
        VRChatAuthCookieStore.pop(CURRENT_USER_ID)

    with patch(
        "homeassistant.components.vrchat.VRChatAPI.logout",
        new=AsyncMock(side_effect=remove_cookie_store),
    ):
        await async_remove_entry(hass, entry)

    assert CURRENT_USER_ID not in VRChatAuthCookieStore


async def test_remove_entry_without_unique_id(hass: HomeAssistant) -> None:
    """Test removing an entry without a unique ID is a no-op."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=None)

    await async_remove_entry(hass, entry)


async def test_remove_entry_continues_after_logout_error(
    hass: HomeAssistant,
) -> None:
    """Test cookie cleanup continues when logout fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )
    cookie_store = VRChatAuthCookieStore.setdefault(
        CURRENT_USER_ID,
        Mock(async_load=AsyncMock(return_value={}), async_remove=AsyncMock()),
    )

    with patch(
        "homeassistant.components.vrchat.VRChatAPI.logout",
        new=AsyncMock(side_effect=RuntimeError("test error")),
    ):
        await async_remove_entry(hass, entry)

    cookie_store.async_remove.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected", "translation_key"),
    [
        pytest.param(
            UnauthorizedException(status=401),
            ConfigEntryAuthFailed,
            "auth_failed",
            id="auth",
        ),
        pytest.param(
            AccountIdMismatch(CURRENT_USER_ID, "wrong"),
            ConfigEntryError,
            "unique_id_mismatch",
            id="identity",
        ),
        pytest.param(
            RuntimeError("failed"),
            VRChatAccountSetupFailed,
            "setup_failed",
            id="connection",
        ),
    ],
)
async def test_start_translates_library_errors(
    hass: HomeAssistant,
    error: Exception,
    expected: type[Exception],
    translation_key: str,
) -> None:
    """Translate library failures at the HA boundary."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    coordinator = VRChatAccountDataCoordinator(hass, entry)
    with (
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAccount.start",
            side_effect=error,
        ),
        pytest.raises(expected) as raised,
    ):
        await coordinator.async_start()
    assert raised.value.translation_key == translation_key
    await coordinator.close()


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        pytest.param(
            RuntimeError("failed"), ConfigEntryState.SETUP_RETRY, id="failure"
        ),
        pytest.param(
            asyncio.CancelledError(), ConfigEntryState.SETUP_ERROR, id="cancel"
        ),
    ],
)
async def test_setup_failure_closes_world_cache(
    hass: HomeAssistant,
    error: BaseException,
    expected_state: ConfigEntryState,
) -> None:
    """Clean up in-flight world requests when account setup fails or is cancelled."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    entry.add_to_hass(hass)
    coordinator = VRChatAccountDataCoordinator(hass, entry)
    InitialCurrentUserData[CURRENT_USER_ID] = {
        **CURRENT_USER,
        "location": "wrld_test:instance",
        "worldId": "wrld_test",
        "instanceId": "instance",
    }
    fetch_started = asyncio.Event()
    fetch_cancelled = asyncio.Event()

    async def fetch_world(_: object, world_id: str) -> Never:
        fetch_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            fetch_cancelled.set()
        raise AssertionError("World request should be cancelled")

    async def get_user(user_id: str) -> Never:
        await fetch_started.wait()
        raise error

    try:
        with (
            patch(
                "homeassistant.components.vrchat.VRChatAccountDataCoordinator",
                return_value=coordinator,
            ),
            patch(
                "homeassistant.components.vrchat.coordinator.VRChatAPI.ws_connect",
                new=AsyncMock(),
            ),
            patch(
                "homeassistant.components.vrchat.coordinator.VRChatAPI.get_user",
                side_effect=get_user,
            ),
            patch(
                "vrchatapi.highlevel.account.VRChatAccount._get_world",
                new=fetch_world,
            ),
        ):
            assert not await hass.config_entries.async_setup(entry.entry_id)

        assert entry.state is expected_state
        assert coordinator.client is not None
        assert coordinator.client.worlds.closed
        assert not coordinator.client.worlds.registry
        assert fetch_cancelled.is_set()
    finally:
        await coordinator.close()


async def test_library_authentication_persists_cookie(hass: HomeAssistant) -> None:
    """Save portable library cookies using Home Assistant storage."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    coordinator = VRChatAccountDataCoordinator(hass, entry)
    coordinator.cookie_store = Mock(async_save=AsyncMock())
    await coordinator._save_cookie(Mock(cookie={"auth": "token"}))
    coordinator.cookie_store.async_save.assert_awaited_once_with({"auth": "token"})


async def test_home_assistant_stop_closes_library(hass: HomeAssistant) -> None:
    """Stop library-owned background work when Home Assistant stops."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    entry.add_to_hass(hass)
    client = Mock(start=AsyncMock(), close=AsyncMock())
    with (
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAccount",
            return_value=client,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    client.close.assert_awaited_once()


@pytest.fixture
async def loaded_entry(hass: HomeAssistant) -> AsyncGenerator[MockConfigEntry]:
    """Load the integration with its real account and mocked network boundaries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )
    entry.add_to_hass(hass)
    InitialCurrentUserData[CURRENT_USER_ID] = CURRENT_USER.copy()
    with (
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.ws_connect",
            new=AsyncMock(side_effect=lambda **kwargs: MockWebSocket()),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_current_user",
            new=AsyncMock(return_value=CURRENT_USER.copy()),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_friends",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_user",
            new=AsyncMock(return_value=FRIEND_USER.copy()),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_deleted_friend_can_be_added_again(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Clear discovery records when a friend is removed, including repeated deletes."""
    coordinator = loaded_entry.runtime_data
    client = coordinator.client
    entity_id = _entity_id(
        entity_registry, f"status.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), loaded_entry.entry_id
    )
    assert device is not None

    await client.handle_event(VRChatEvent("friend-delete", {"userId": FRIEND_USER_ID}))
    await client.handle_event(VRChatEvent("friend-delete", {"userId": FRIEND_USER_ID}))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None
    assert device_registry.async_get(device.id) is None

    await client.handle_event(
        VRChatEvent("friend-active", {"userId": FRIEND_USER_ID, "user": FRIEND_USER})
    )
    await hass.async_block_till_done()

    assert (
        _entity_id(entity_registry, f"status.{CURRENT_USER_ID}:{FRIEND_USER_ID}")
        == entity_id
    )
    assert hass.states.get(entity_id).state == "active"
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), loaded_entry.entry_id
        )
        is not None
    )


async def test_late_sensor_field_and_duplicate_updates(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Discover a sensor once when an existing user's previously absent field arrives."""
    client = loaded_entry.runtime_data.client
    await client.handle_event(VRChatEvent("friend-delete", {"userId": FRIEND_USER_ID}))
    await hass.async_block_till_done()
    friend = FRIEND_USER.copy()
    friend.pop("statusDescription")
    with patch.object(client.api, "get_user", new=AsyncMock(return_value=friend)):
        await client.handle_event(
            VRChatEvent("friend-active", {"userId": FRIEND_USER_ID, "user": friend})
        )
    await hass.async_block_till_done()
    unique_id = f"statusDescription.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    assert entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id) is None
    listeners_before = len(loaded_entry.runtime_data._listeners)
    event = VRChatEvent(
        "friend-update",
        {"userId": FRIEND_USER_ID, "user": {"statusDescription": "New description"}},
    )

    await client.handle_event(event)
    await hass.async_block_till_done()
    entity_id = _entity_id(entity_registry, unique_id)
    assert hass.states.get(entity_id).state == "New description"
    assert len(loaded_entry.runtime_data._listeners) == listeners_before + 1

    await client.handle_event(event)
    await client.handle_event(event)
    await hass.async_block_till_done()
    assert _entity_id(entity_registry, unique_id) == entity_id
    assert len(loaded_entry.runtime_data._listeners) == listeners_before + 1


async def test_push_updates_only_affected_user(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Unchanged states must not be reported again for unrelated friends."""
    entity_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)
    reports: list[str] = []

    @callback
    def record_report(event: Event) -> None:
        reports.append(event.data["entity_id"])

    remove_report = async_track_state_report_event(hass, entity_ids, record_report)
    remove_change = async_track_state_change_event(hass, entity_ids, record_report)
    await loaded_entry.runtime_data.client.handle_event(
        VRChatEvent(
            "friend-update",
            {"userId": FRIEND_USER_ID, "user": {"displayName": "Renamed friend"}},
        )
    )
    await hass.async_block_till_done()
    remove_report()
    remove_change()

    assert set(reports) == {
        _entity_id(entity_registry, f"{key}.{CURRENT_USER_ID}:{FRIEND_USER_ID}")
        for key in ("state", "status", "statusDescription", "location")
    }
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), loaded_entry.entry_id
    )
    assert device is not None
    assert device.name == "Renamed friend"


async def test_world_updates_only_location_sensor(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Resolved metadata updates the location without reporting other data again."""
    client = loaded_entry.runtime_data.client
    world = {"id": "wrld_test", "name": "First world"}
    await client.handle_event(
        VRChatEvent(
            "friend-location",
            {
                "userId": FRIEND_USER_ID,
                "user": {"status": "active"},
                "location": "wrld_test:instance",
                "world": world,
            },
        )
    )
    await hass.async_block_till_done()
    reports: list[str] = []

    @callback
    def record_report(event: Event) -> None:
        reports.append(event.data["entity_id"])

    entity_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)
    remove_report = async_track_state_report_event(hass, entity_ids, record_report)
    remove_change = async_track_state_change_event(hass, entity_ids, record_report)
    client.worlds.get("wrld_test", {"id": "wrld_test", "name": "Renamed world"})
    await hass.async_block_till_done()
    remove_report()
    remove_change()

    entity_id = _entity_id(
        entity_registry, f"location.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    )
    assert set(reports) == {entity_id}
    assert hass.states.get(entity_id).state == "Renamed world"


async def test_async_world_lookup_updates_location(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Publish world names and thumbnails after an in-flight SDK fetch resolves."""
    fetch_started = asyncio.Event()
    fetch_released = asyncio.Event()

    async def fetch_world(world_id: str) -> World:
        fetch_started.set()
        await fetch_released.wait()
        return {
            "id": world_id,
            "name": "Resolved world",
            "thumbnailImageUrl": "https://example.com/world.png",
        }

    with patch.object(loaded_entry.runtime_data.client.api, "get_world", fetch_world):
        await loaded_entry.runtime_data.client.handle_event(
            VRChatEvent(
                "friend-location",
                {
                    "userId": FRIEND_USER_ID,
                    "user": {"status": "active"},
                    "location": "wrld_test:instance",
                },
            )
        )
        await fetch_started.wait()
        fetch_released.set()
        await hass.async_block_till_done()

    entity_id = _entity_id(
        entity_registry, f"location.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    )
    state = hass.states.get(entity_id)
    assert state.state == "Resolved world"
    assert state.attributes["entity_picture"] == "https://example.com/world.png"
    assert state.attributes["instanceId"] == "instance"


async def test_disconnect_and_reconnect_update_availability(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Connection notifications make every entity unavailable and restore its state."""
    previous_states = {
        state.entity_id: state.state for state in hass.states.async_all(SENSOR_DOMAIN)
    }
    loaded_entry.runtime_data.client._set_available(False)
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all(SENSOR_DOMAIN)} == {
        STATE_UNAVAILABLE
    }

    loaded_entry.runtime_data.client._set_available(True)
    await hass.async_block_till_done()
    assert {
        state.entity_id: state.state for state in hass.states.async_all(SENSOR_DOMAIN)
    } == previous_states


async def test_push_during_disconnect_does_not_restore_availability(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A pushed snapshot must not restore availability before the SDK reconnects."""
    client = loaded_entry.runtime_data.client
    client._set_available(False)
    await hass.async_block_till_done()

    await client.handle_event(
        VRChatEvent(
            "friend-update",
            {"userId": FRIEND_USER_ID, "user": {"status": "busy"}},
        )
    )
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all(SENSOR_DOMAIN)} == {
        STATE_UNAVAILABLE
    }

    client._set_available(True)
    await hass.async_block_till_done()
    entity_id = _entity_id(
        entity_registry, f"status.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    )
    assert hass.states.get(entity_id).state == "busy"
    assert STATE_UNAVAILABLE not in {
        state.state for state in hass.states.async_all(SENSOR_DOMAIN)
    }


async def test_reload_removes_old_listeners(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Unloading removes platform and entity subscriptions before a fresh load."""
    coordinator = loaded_entry.runtime_data
    listener_count = len(coordinator._listeners)
    assert listener_count > 1
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator._listeners
    assert coordinator.client.closed
    assert coordinator.client.worlds.closed

    assert await hass.config_entries.async_setup(loaded_entry.entry_id)
    await hass.async_block_till_done()
    replacement = loaded_entry.runtime_data
    assert replacement is not coordinator
    assert len(replacement._listeners) == listener_count
    await coordinator.close()
    assert not coordinator._listeners
    assert replacement.client.available


async def test_shared_friend_is_isolated_between_accounts(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The same VRChat user has independent entities and devices for each account."""
    other_id = "usr_other"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "other@example.com", CONF_PASSWORD: "password"},
        unique_id=other_id,
    )
    entry.add_to_hass(hass)
    InitialCurrentUserData[other_id] = {**CURRENT_USER, "id": other_id}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    first_entity_id = _entity_id(
        entity_registry, f"status.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
    )
    second_entity_id = _entity_id(
        entity_registry, f"status.{other_id}:{FRIEND_USER_ID}"
    )
    assert first_entity_id != second_entity_id
    first_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), loaded_entry.entry_id
    )
    second_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{other_id}:{FRIEND_USER_ID}"), entry.entry_id
    )
    assert first_device is not None
    assert second_device is not None
    assert first_device.id != second_device.id

    await loaded_entry.runtime_data.client.handle_event(
        VRChatEvent(
            "friend-update", {"userId": FRIEND_USER_ID, "user": {"status": "busy"}}
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(first_entity_id).state == "busy"
    assert hass.states.get(second_entity_id).state == "active"

    await loaded_entry.runtime_data.client.handle_event(
        VRChatEvent("friend-delete", {"userId": FRIEND_USER_ID})
    )
    await hass.async_block_till_done()
    assert hass.states.get(first_entity_id) is None
    assert hass.states.get(second_entity_id).state == "active"
    assert device_registry.async_get(second_device.id) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
