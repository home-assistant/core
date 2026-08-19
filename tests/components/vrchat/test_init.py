"""Test the VRChat integration setup and updates."""

import asyncio
import json
import logging
from typing import Never, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
import vrchatapi

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vrchat import async_remove_entry
from homeassistant.components.vrchat.api_data_types import CurrentUser
from homeassistant.components.vrchat.const import DOMAIN
from homeassistant.components.vrchat.coordinator import (
    VRChatAccountDataCoordinator,
    VRChatAccountSetupFailed,
    VRChatUserDataCoordinator,
)
from homeassistant.components.vrchat.store import (
    InitialCurrentUserData,
    VRChatAuthCookieStore,
)
from homeassistant.components.vrchat.utils import AsyncCleanups, is_user_in_game
from homeassistant.config_entries import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryState,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
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
    "currentAvatarThumbnailImageUrl": "https://example.com/friend-avatar.png",
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


async def test_async_cleanups_uses_callback_snapshot() -> None:
    """Test cleanup callbacks can unregister other callbacks."""
    cleanups = AsyncCleanups()
    second_cleanup = Mock()

    def first_cleanup() -> None:
        cleanups.remove_from_cleanups(second_cleanup)

    cleanups.add_to_cleanups(second_cleanup)
    cleanups.add_to_cleanups(first_cleanup)

    await cleanups.close()

    second_cleanup.assert_called_once()


async def test_async_cleanups_timeout_does_not_stop_other_callbacks() -> None:
    """Test a timed out cleanup does not stop other cleanup callbacks."""
    cleanups = AsyncCleanups()
    completed_cleanup = Mock()
    cleanup_started = asyncio.Event()

    async def stuck_cleanup() -> None:
        cleanup_started.set()
        await asyncio.Event().wait()

    cleanups.add_to_cleanups(completed_cleanup)
    cleanups.add_to_cleanups(stuck_cleanup)

    with patch("homeassistant.components.vrchat.utils.ASYNC_CLEANUP_TIMEOUT_SECOND", 0):
        await cleanups.close()

    assert cleanup_started.is_set()
    completed_cleanup.assert_called_once()


async def test_restart_closes_replacement_api() -> None:
    """Test restarting closes both the old and replacement API clients."""
    old_api = Mock()
    old_api.close = AsyncMock()
    replacement_api = Mock()
    replacement_api.close = AsyncMock()
    old_api.copy.return_value = replacement_api

    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.api = old_api
    coordinator.auto_restart = False
    coordinator.authenticate = AsyncMock()
    coordinator.ws_connect = AsyncMock()
    coordinator.fetch_users = AsyncMock()
    coordinator.add_to_cleanups(old_api.close)

    await coordinator._restart(0)

    old_api.close.assert_awaited_once()
    assert replacement_api.close in coordinator._cleanups

    await AsyncCleanups.close(coordinator)

    replacement_api.close.assert_awaited_once()


async def test_restart_does_not_cancel_current_task() -> None:
    """Test a restarting task is allowed to finish its cleanup."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    current_task = asyncio.current_task()
    assert current_task is not None
    replacement_task = Mock()

    def create_task(coro: object) -> Mock:
        coro.close()
        return replacement_task

    coordinator.current_user_data = {"username": "current_user"}
    coordinator.starting_task = current_task
    coordinator.create_task = create_task

    assert coordinator.restart() is replacement_task
    assert current_task.cancelling() == 0


async def test_cleanup_cancels_current_starting_task() -> None:
    """Test cleanup cancels the startup task that replaced the original task."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    original_task = Mock()
    current_task = Mock()
    coordinator.starting_task = original_task
    coordinator.add_to_cleanups(coordinator._cancel_starting_task)
    coordinator.starting_task = current_task

    await AsyncCleanups.close(coordinator)

    current_task.cancel.assert_called_once()
    original_task.cancel.assert_not_called()


async def test_use_api_closes_temporary_api() -> None:
    """Test using an API copy closes it after a successful callback."""
    primary_api = Mock()
    temporary_api = Mock()
    temporary_api.close = AsyncMock()
    primary_api.copy.return_value = temporary_api
    callback = AsyncMock(return_value="result")

    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.api = primary_api

    assert await coordinator.use_api(callback) == "result"

    callback.assert_awaited_once_with(temporary_api)
    temporary_api.close.assert_awaited_once()


async def test_use_api_closes_temporary_api_after_error() -> None:
    """Test using an API copy closes it when the callback fails."""
    primary_api = Mock()
    temporary_api = Mock()
    temporary_api.close = AsyncMock()
    primary_api.copy.return_value = temporary_api
    callback = AsyncMock(side_effect=RuntimeError("test error"))

    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.api = primary_api

    with pytest.raises(RuntimeError, match="test error"):
        await coordinator.use_api(callback)

    temporary_api.close.assert_awaited_once()


async def test_use_api_reauthenticates_after_closing_temporary_api() -> None:
    """Test authentication errors close the temporary API before retrying."""
    primary_api = Mock()
    temporary_api = Mock()
    temporary_api.close = AsyncMock()
    primary_api.copy.return_value = temporary_api
    callback = AsyncMock(
        side_effect=[
            vrchatapi.exceptions.UnauthorizedException(status=401, reason="expired"),
            "result",
        ]
    )

    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.api = primary_api
    coordinator.restart = AsyncMock()

    assert await coordinator.use_api(callback) == "result"

    temporary_api.close.assert_awaited_once()
    coordinator.restart.assert_awaited_once()
    assert callback.await_args_list[0].args == (temporary_api,)
    assert callback.await_args_list[1].args == (primary_api,)


async def test_authenticate_saves_current_user_and_cookie() -> None:
    """Test authenticating stores current user data and cookies."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.config_entry = entry
    coordinator.api = Mock(
        get_current_user=AsyncMock(return_value=CURRENT_USER.copy()),
        cookie={"auth": "cookie"},
    )
    coordinator.cookie_store = Mock(async_save=AsyncMock())

    await coordinator.authenticate()

    assert coordinator.current_user_data["id"] == CURRENT_USER_ID
    coordinator.cookie_store.async_save.assert_awaited_once_with({"auth": "cookie"})


async def test_authenticate_rejects_mismatched_user() -> None:
    """Test authentication rejects a response for another user."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.config_entry = entry
    coordinator.api = Mock(get_current_user=AsyncMock(return_value={"id": "usr_other"}))

    with pytest.raises(ConfigEntryError):
        await coordinator.authenticate()


async def test_authenticate_translates_unexpected_error() -> None:
    """Test unexpected authentication errors become setup failures."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CURRENT_USER_ID)
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.config_entry = entry
    coordinator.api = Mock(
        get_current_user=AsyncMock(side_effect=RuntimeError("test error"))
    )

    with pytest.raises(VRChatAccountSetupFailed):
        await coordinator.authenticate()


async def test_ensure_user_returns_existing_user() -> None:
    """Test ensuring an existing user does not fetch it again."""
    user = Mock()
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.users = {FRIEND_USER_ID: user}
    coordinator.api = Mock(get_user=AsyncMock())

    assert await coordinator.ensure_user(FRIEND_USER_ID) is user
    coordinator.api.get_user.assert_not_awaited()


async def test_ensure_user_fetches_missing_user() -> None:
    """Test ensuring a missing user fetches and stores it."""
    user = Mock()
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.users = {}
    coordinator.api = Mock(get_user=AsyncMock(return_value=FRIEND_USER.copy()))
    coordinator.set_user = Mock(return_value=user)

    assert await coordinator.ensure_user(FRIEND_USER_ID) is user
    coordinator.api.get_user.assert_awaited_once_with(FRIEND_USER_ID)
    coordinator.set_user.assert_called_once_with(FRIEND_USER, False)


def test_available_notifies_users_on_change() -> None:
    """Test account availability changes notify all users."""
    first_user = Mock()
    second_user = Mock()
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator._available = False
    coordinator.username = "current_user"
    coordinator.users = {"first": first_user, "second": second_user}

    coordinator.available = True

    assert coordinator.available
    first_user.async_update_entities.assert_called_once_with(force_refresh=True)
    second_user.async_update_entities.assert_called_once_with(force_refresh=True)


async def test_fetch_users_sets_online_and_offline_friends() -> None:
    """Test fetched online and offline friends are added to the account."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.current_user_data = {
        "id": CURRENT_USER_ID,
        "friends": [FRIEND_USER_ID, NEW_FRIEND_USER_ID],
    }
    coordinator.users = {}
    coordinator.set_user = Mock()
    coordinator._get_friends = AsyncMock(
        side_effect=[[FRIEND_USER.copy()], [NEW_FRIEND_USER.copy()]]
    )

    await coordinator.fetch_users()

    assert coordinator.set_user.call_args_list[0].args == (
        coordinator.current_user_data,
    )
    assert coordinator.set_user.call_args_list[1].args == (NEW_FRIEND_USER,)
    assert coordinator.set_user.call_args_list[2].args == (FRIEND_USER,)


async def test_websocket_handler_task_cleanup_is_removed_when_done(
    hass: HomeAssistant,
) -> None:
    """Test completed websocket handler tasks are removed from cleanup."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    task = asyncio.create_task(asyncio.sleep(0))

    coordinator._track_ws_handler_task(task)

    assert task.cancel in coordinator._cleanups

    await task
    await hass.async_block_till_done()

    assert task.cancel not in coordinator._cleanups


async def test_websocket_error_handler_logs_callback_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test WebSocket callback errors retain their exception information."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    error = RuntimeError("test error")

    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.vrchat.coordinator"
    ):
        await coordinator._ws_error_handler(error)

    assert caplog.records[0].exc_info == (RuntimeError, error, None)


def test_cancelled_replaced_websocket_handler_does_not_restart() -> None:
    """Test cancelling a replaced WebSocket handler does not restart it."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    old_websocket = object()
    coordinator.ws = object()
    coordinator.auto_restart = True
    coordinator.restart = Mock()
    task = Mock()
    task.result.side_effect = asyncio.CancelledError

    coordinator.ws_handler_done(old_websocket)(task)

    coordinator.restart.assert_not_called()


def test_cancelled_current_websocket_handler_does_not_restart() -> None:
    """Test cancelling the current WebSocket handler does not restart it."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    websocket = object()
    coordinator.ws = websocket
    coordinator.auto_restart = True
    coordinator.restart = Mock()
    task = Mock()
    task.result.side_effect = asyncio.CancelledError

    coordinator.ws_handler_done(websocket)(task)

    coordinator.restart.assert_not_called()


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


async def test_get_friends_propagates_fetch_error() -> None:
    """Test friend fetch errors propagate from the task group."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.current_user_data = {"onlineFriends": [FRIEND_USER_ID]}
    coordinator.api = Mock()
    coordinator.api.get_friends = AsyncMock(side_effect=RuntimeError("test error"))

    with pytest.raises(ExceptionGroup) as exc_info:
        await coordinator._get_friends(False)

    assert isinstance(exc_info.value.exceptions[0], RuntimeError)
    assert str(exc_info.value.exceptions[0]) == "test error"


async def test_fetch_users_propagates_missing_friend_fetch_error() -> None:
    """Test missing friend fetch errors propagate from the task group."""
    coordinator = object.__new__(VRChatAccountDataCoordinator)
    coordinator.current_user_data = cast(
        CurrentUser,
        {
            "id": CURRENT_USER_ID,
            "friends": [FRIEND_USER_ID],
            "onlineFriends": [],
            "offlineFriends": [],
        },
    )
    coordinator.users = {}
    coordinator.api = Mock()
    coordinator.api.get_friends = AsyncMock(return_value=[])
    coordinator.api.get_user = AsyncMock(side_effect=RuntimeError("test error"))

    with (
        patch.object(VRChatAccountDataCoordinator, "set_user"),
        pytest.raises(ExceptionGroup) as exc_info,
    ):
        await coordinator.fetch_users()

    assert isinstance(exc_info.value.exceptions[0], RuntimeError)
    assert str(exc_info.value.exceptions[0]) == "test error"


@pytest.mark.parametrize(
    ("user_data", "expected"),
    [
        pytest.param({}, None, id="missing_location"),
        pytest.param({"location": "offline"}, False, id="offline"),
        pytest.param({"location": "offline:offline"}, False, id="offline_location"),
        pytest.param(
            {"location": "wrld_offline"}, True, id="world_id_contains_offline"
        ),
        pytest.param({"location": "wrld_123"}, True, id="in_world"),
        pytest.param({"location": ""}, None, id="empty_location"),
        pytest.param(
            {"presence": {"location": "wrld_123"}},
            None,
            id="presence_location_is_not_used",
        ),
    ],
)
def test_is_user_in_game_matches_original_binary_sensor(
    user_data: dict[str, object], expected: bool | None
) -> None:
    """Test that the shared presence logic matches the removed binary sensor."""
    assert is_user_in_game(user_data) is expected


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
            new=AsyncMock(return_value=FRIEND_USER.copy()),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_api_close,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        state_entity_id = _entity_id(
            entity_registry, f"state.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
        )
        assert hass.states.get(state_entity_id).state == "offline"
        assert (
            hass.states.get(state_entity_id).attributes["entity_picture"]
            == "https://example.com/current-icon.png"
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
        coordinator._handle_ws_message(
            {
                "type": "user-update",
                "content": json.dumps(
                    {"userId": FRIEND_USER_ID, "user": {"status": "ask me"}}
                ),
            }
        )
        await hass.async_block_till_done()
        assert hass.states.get(status_entity_id).state == "ask_me"

        coordinator._handle_ws_message(
            {
                "type": "friend-active",
                "content": json.dumps(
                    {"userId": NEW_FRIEND_USER_ID, "user": NEW_FRIEND_USER}
                ),
            }
        )
        await hass.async_block_till_done()
        new_friend_status_entity_id = _entity_id(
            entity_registry,
            f"status.{CURRENT_USER_ID}:{NEW_FRIEND_USER_ID}",
        )
        assert hass.states.get(new_friend_status_entity_id).state == "busy"
        new_friend_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{CURRENT_USER_ID}:{NEW_FRIEND_USER_ID}"), entry.entry_id
        )
        assert new_friend_device is not None

        coordinator._handle_ws_message(
            {
                "type": "friend-delete",
                "content": json.dumps({"userId": NEW_FRIEND_USER_ID}),
            }
        )
        await hass.async_block_till_done()
        assert NEW_FRIEND_USER_ID not in coordinator.users
        assert device_registry.async_get(new_friend_device.id) is None

        coordinator.current_user_data["friends"] = []
        await coordinator.fetch_users()
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
