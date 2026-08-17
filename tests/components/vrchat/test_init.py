"""Test the VRChat integration setup and updates."""

import asyncio
import json
from typing import Never
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vrchat import async_remove_entry
from homeassistant.components.vrchat.const import DOMAIN
from homeassistant.components.vrchat.coordinator import (
    VRChatAccountAuthFailed,
    VRChatAccountSetupFailed,
)
from homeassistant.components.vrchat.store import (
    InitialCurrentUserData,
    VRChatAuthCookieStore,
)
from homeassistant.components.vrchat.utils import is_user_in_game
from homeassistant.config_entries import ConfigEntryState
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


@pytest.mark.parametrize(
    ("exception_class", "translation_key"),
    [
        pytest.param(VRChatAccountAuthFailed, "auth_failed", id="auth_failed"),
        pytest.param(VRChatAccountSetupFailed, "setup_failed", id="setup_failed"),
    ],
)
def test_account_exception_translations(
    exception_class: type[VRChatAccountAuthFailed | VRChatAccountSetupFailed],
    translation_key: str,
) -> None:
    """Test account exceptions use registered translation keys."""
    entry = MockConfigEntry(domain=DOMAIN, title="current_user")

    exception = exception_class(entry)

    assert exception.translation_domain == DOMAIN
    assert exception.translation_key == translation_key
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
            entity_registry, f"vrchat.state.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
        )
        assert hass.states.get(state_entity_id).state == "offline"
        assert (
            hass.states.get(state_entity_id).attributes["entity_picture"]
            == "https://example.com/current-icon.png"
        )
        current_user_status_entity_id = _entity_id(
            entity_registry, f"vrchat.status.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
        )
        assert hass.states.get(current_user_status_entity_id).state == "offline"
        status_description_entity_id = _entity_id(
            entity_registry,
            f"vrchat.statusDescription.{CURRENT_USER_ID}:{FRIEND_USER_ID}",
        )
        assert (
            entity_registry.async_get(status_description_entity_id).translation_key
            == "status_description"
        )
        assert (
            hass.states.get(status_description_entity_id).state == "Friend description"
        )
        status_entity_id = _entity_id(
            entity_registry, f"vrchat.status.{CURRENT_USER_ID}:{FRIEND_USER_ID}"
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
            f"vrchat.status.{CURRENT_USER_ID}:{NEW_FRIEND_USER_ID}",
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
