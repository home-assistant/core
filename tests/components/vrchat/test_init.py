"""Test the VRChat integration setup and updates."""

import asyncio
from typing import Never
from unittest.mock import AsyncMock, Mock, patch

import pytest
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.highlevel import AccountIdMismatch
from vrchatapi.websocket import VRChatEvent

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vrchat import async_remove_entry
from homeassistant.components.vrchat.const import DOMAIN, USER_AGENT
from homeassistant.components.vrchat.coordinator import (
    VRChatAccountDataCoordinator,
    VRChatAccountSetupFailed,
    VRChatUserDataCoordinator,
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
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

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


def test_entity_update_listener_snapshot() -> None:
    """Test removing a listener during an update does not skip later listeners."""
    coordinator = object.__new__(VRChatUserDataCoordinator)
    second_listener = Mock()

    def remove_second_listener(_: bool, __: bool) -> None:
        coordinator._entity_update_listeners.remove(second_listener)

    coordinator._entity_update_listeners = [remove_second_listener, second_listener]

    coordinator.async_update_entities(True)

    second_listener.assert_called_once_with(True, False)


def test_entity_update_listener_removal_is_idempotent() -> None:
    """Test removing an entity update listener multiple times is safe."""
    coordinator = object.__new__(VRChatUserDataCoordinator)
    coordinator._entity_update_listeners = []

    remove_listener = coordinator.async_add_entity_update_listener(Mock())

    remove_listener()
    remove_listener()

    assert not coordinator._entity_update_listeners


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
        assert "entity_picture" in hass.states.get(status_entity_id).attributes

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
        assert coordinator.users[NEW_FRIEND_USER_ID].data["location"] == (
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
        assert NEW_FRIEND_USER_ID not in coordinator.users
        assert device_registry.async_get(new_friend_device.id) is None

        coordinator.client.current_user_data["friends"] = []
        await coordinator.client.fetch_users()
        assert FRIEND_USER_ID not in coordinator.users

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


def test_library_availability_updates_entities() -> None:
    """Forward connection availability to existing entities."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    user = Mock()
    coordinator.users = {FRIEND_USER_ID: user}
    coordinator._availability_updated(False)
    user.async_update_entities.assert_called_once_with(force_refresh=False)


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
