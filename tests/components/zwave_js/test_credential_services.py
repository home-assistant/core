"""Tests for Z-Wave JS credential management services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from zwave_js_server.const.command_class.access_control import UserCredentialType
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import SCHLAGE_BE469_LOCK_ENTITY

from tests.common import MockConfigEntry


def _mock_access_control(node: Node) -> MagicMock:
    """Inject a mock AccessControlAPI into the node's endpoint 0."""
    api = MagicMock()
    api.async_is_supported = AsyncMock(return_value=True)

    # Mock UserCapabilities
    user_caps = MagicMock()
    user_caps.max_users = 20
    user_caps.supported_user_types = []
    user_caps.max_user_name_length = 20
    user_caps.supported_credential_rules = []
    api.async_get_user_capabilities_cached = AsyncMock(return_value=user_caps)

    # Mock CredentialCapabilities
    cred_caps = MagicMock()
    cred_caps.supported_credential_types = {}
    cred_caps.supports_admin_code = False
    cred_caps.supports_admin_code_deactivation = False
    api.async_get_credential_capabilities_cached = AsyncMock(return_value=cred_caps)

    # Mock user operations
    api.async_get_users_cached = AsyncMock(return_value=[])
    api.async_get_user_cached = AsyncMock(return_value=None)
    api.async_set_user = AsyncMock(return_value=None)
    api.async_delete_user = AsyncMock(return_value=None)
    api.async_delete_all_users = AsyncMock(return_value=None)

    # Mock credential operations
    api.async_get_credentials_cached = AsyncMock(return_value=[])
    api.async_get_credential_cached = AsyncMock(return_value=None)
    api.async_set_credential = AsyncMock(return_value=None)
    api.async_delete_credential = AsyncMock(return_value=None)

    # cached_property: override via instance __dict__
    node.endpoints[0].__dict__["access_control"] = api
    return api


async def test_set_user_auto_find(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user with auto-find user slot."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "set_user",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_name": "Alice",
            "user_type": "general",
            "active": True,
        },
        blocking=True,
    )

    api.async_set_user.assert_called_once()
    call_args = api.async_set_user.call_args
    assert call_args[0][0] == 1  # auto-found user_id


async def test_set_user_explicit_index(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user with explicit user index."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "set_user",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 5,
            "user_name": "Bob",
        },
        blocking=True,
    )

    api.async_set_user.assert_called_once()
    call_args = api.async_set_user.call_args
    assert call_args[0][0] == 5


async def test_set_user_no_slots(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user fails when no user slots available."""
    api = _mock_access_control(lock_schlage_be469)

    # Fill all slots
    user_caps = api.async_get_user_capabilities_cached.return_value
    user_caps.max_users = 2
    user1 = MagicMock()
    user1.user_id = 1
    user2 = MagicMock()
    user2.user_id = 2
    api.async_get_users_cached.return_value = [user1, user2]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_user",
            {
                ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
                "user_name": "Charlie",
            },
            blocking=True,
        )


async def test_clear_user(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_user deletes a single user."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_user",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 3,
        },
        blocking=True,
    )

    api.async_delete_user.assert_called_once_with(3)


async def test_clear_all_users(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_all_users deletes all users."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_all_users",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
        },
        blocking=True,
    )

    api.async_delete_all_users.assert_called_once()


async def test_get_credential_capabilities(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_capabilities returns capability data."""
    _mock_access_control(lock_schlage_be469)

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_capabilities",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    assert data["supports_user_management"] is True
    assert data["max_users"] == 20


async def test_get_credential_capabilities_not_supported(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_capabilities fails when not supported."""
    api = _mock_access_control(lock_schlage_be469)
    api.async_is_supported.return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_credential_capabilities",
            {
                ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            },
            blocking=True,
            return_response=True,
        )


async def test_get_users(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_users returns user list."""
    api = _mock_access_control(lock_schlage_be469)

    user = MagicMock()
    user.user_id = 1
    user.user_name = "Alice"
    user.active = True
    user.user_type = MagicMock()
    user.credential_rule = None
    api.async_get_users_cached.return_value = [user]
    api.async_get_credentials_cached.return_value = []

    result = await hass.services.async_call(
        DOMAIN,
        "get_users",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    assert data["max_users"] == 20
    assert len(data["users"]) == 1
    assert data["users"][0]["user_index"] == 1
    assert data["users"][0]["user_name"] == "Alice"
    assert data["users"][0]["active"] is True


async def test_set_credential_auto_find(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with auto-find user and slot."""
    api = _mock_access_control(lock_schlage_be469)

    # Set up credential capabilities with a PIN type
    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 10
    cred_caps = api.async_get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {UserCredentialType.PIN_CODE: pin_cap}

    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "credential_type": "pin_code",
            "credential_data": "1234",
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    # Should have created a new user (auto-find) and set credential
    api.async_set_user.assert_called_once()
    api.async_set_credential.assert_called_once()
    assert data["user_index"] == 1
    assert data["credential_slot"] == 1


async def test_set_credential_explicit_user(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with explicit user index."""
    api = _mock_access_control(lock_schlage_be469)

    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "credential_type": "pin_code",
            "credential_data": "5678",
            "user_index": 3,
            "credential_slot": 2,
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    # Should NOT have created a new user
    api.async_set_user.assert_not_called()
    api.async_set_credential.assert_called_once()
    assert data["user_index"] == 3
    assert data["credential_slot"] == 2


async def test_set_credential_with_user_type(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential forwards user_type to set_user when creating user."""
    api = _mock_access_control(lock_schlage_be469)

    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 10
    cred_caps = api.async_get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {UserCredentialType.PIN_CODE: pin_cap}

    await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "credential_type": "pin_code",
            "credential_data": "9999",
            "user_type": "general",
            "active": True,
        },
        blocking=True,
        return_response=True,
    )

    # Should have created user with user_type forwarded
    api.async_set_user.assert_called_once()
    call_args = api.async_set_user.call_args
    options = call_args[0][1]
    assert options.active is True


async def test_clear_credential(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_credential deletes a single credential."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_credential",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 2,
        },
        blocking=True,
    )

    api.async_delete_credential.assert_called_once()


async def test_clear_all_credentials(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_all_credentials deletes all credentials for a user."""
    api = _mock_access_control(lock_schlage_be469)

    # Set up existing credentials
    cred1 = MagicMock()
    cred1.type = MagicMock()
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = MagicMock()
    cred2.slot = 2
    api.async_get_credentials_cached.return_value = [cred1, cred2]

    await hass.services.async_call(
        DOMAIN,
        "clear_all_credentials",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 1,
        },
        blocking=True,
    )

    assert api.async_delete_credential.call_count == 2


async def test_get_credential_status_exists(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_status when credential exists."""
    api = _mock_access_control(lock_schlage_be469)

    cred = MagicMock()
    cred.user_id = 1
    api.async_get_credential_cached.return_value = cred

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_status",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 1,
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    assert data["credential_exists"] is True
    assert data["user_index"] == 1
    assert data["credential_type"] == "pin_code"
    assert data["credential_slot"] == 1


async def test_get_credential_status_not_exists(
    hass: HomeAssistant,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_status when credential does not exist."""
    api = _mock_access_control(lock_schlage_be469)
    api.async_get_credential_cached.return_value = None

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_status",
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 5,
        },
        blocking=True,
        return_response=True,
    )

    data = result[SCHLAGE_BE469_LOCK_ENTITY]
    assert data["credential_exists"] is False
