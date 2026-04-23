"""Tests for Z-Wave JS credential management services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from zwave_js_server.const.command_class.access_control import (
    SetCredentialResult,
    SetUserResult,
    UserCredentialType,
    UserCredentialUserType,
)
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _mock_access_control(node: Node) -> MagicMock:
    """Inject a mock AccessControlAPI into the node's endpoint 0."""
    api = MagicMock()
    api.async_is_supported = AsyncMock(return_value=True)

    user_caps = MagicMock()
    user_caps.max_users = 20
    user_caps.supported_user_types = [UserCredentialUserType.GENERAL]
    user_caps.max_user_name_length = 20
    user_caps.supported_credential_rules = []
    api.async_get_user_capabilities_cached = AsyncMock(return_value=user_caps)

    cred_caps = MagicMock()
    cred_caps.supported_credential_types = {}
    cred_caps.supports_admin_code = False
    cred_caps.supports_admin_code_deactivation = False
    api.async_get_credential_capabilities_cached = AsyncMock(return_value=cred_caps)

    api.async_get_users_cached = AsyncMock(return_value=[])
    api.async_get_user_cached = AsyncMock(return_value=None)
    api.async_set_user = AsyncMock(return_value=SetUserResult.OK)
    api.async_delete_user = AsyncMock(return_value=SetUserResult.OK)
    api.async_delete_all_users = AsyncMock(return_value=SetUserResult.OK)

    api.async_get_credentials_cached = AsyncMock(return_value=[])
    api.async_get_credentials_by_type_cached = AsyncMock(return_value=[])
    api.async_get_all_credentials_cached = AsyncMock(return_value=[])
    api.async_get_credential_cached = AsyncMock(return_value=None)
    api.async_set_credential = AsyncMock(return_value=SetCredentialResult.OK)
    api.async_delete_credential = AsyncMock(return_value=SetCredentialResult.OK)

    # cached_property: override via instance __dict__
    node.endpoints[0].__dict__["access_control"] = api
    return api


def _device_id(device_registry: dr.DeviceRegistry, client, node: Node) -> str:
    """Resolve the HA device_id for a mocked Z-Wave node."""
    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, node)}
    )
    assert device is not None
    return device.id


def _lock_entity_id(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    node: Node,
) -> str:
    """Resolve the HA lock entity_id for a mocked Z-Wave node."""
    device_id = _device_id(device_registry, client, node)
    for entry in entity_registry.entities.values():
        if entry.device_id == device_id and entry.entity_id.startswith("lock."):
            return entry.entity_id
    raise AssertionError(f"No lock entity found for device {device_id}")


async def test_set_user_auto_find(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user with auto-find user slot returns allocated user_index."""
    api = _mock_access_control(lock_schlage_be469)
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_user",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_name": "Alice",
            "user_type": "general",
            "active": True,
        },
        blocking=True,
        return_response=True,
    )

    api.async_set_user.assert_called_once()
    call_args = api.async_set_user.call_args
    assert call_args[0][0] == 1  # auto-found user_id
    assert result[entity_id]["user_index"] == 1


async def test_set_user_explicit_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user with explicit user index echoes it back."""
    api = _mock_access_control(lock_schlage_be469)
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_user",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_index": 5,
            "user_name": "Bob",
        },
        blocking=True,
        return_response=True,
    )

    api.async_set_user.assert_called_once()
    call_args = api.async_set_user.call_args
    assert call_args[0][0] == 5
    assert result[entity_id]["user_index"] == 5


async def test_set_user_no_slots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user fails when no user slots available."""
    api = _mock_access_control(lock_schlage_be469)

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
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_name": "Charlie",
            },
            blocking=True,
            return_response=True,
        )


async def test_clear_user(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_user deletes a single user."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_user",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_index": 3,
        },
        blocking=True,
    )

    api.async_delete_user.assert_called_once_with(3)


async def test_clear_all_users(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_all_users deletes all users."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_all_users",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
        },
        blocking=True,
    )

    api.async_delete_all_users.assert_called_once()


async def test_get_credential_capabilities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_capabilities returns capability data."""
    _mock_access_control(lock_schlage_be469)
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_capabilities",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[entity_id]["supports_user_management"] is True
    assert result[entity_id]["max_users"] == 20
    assert result[entity_id]["supported_user_types"] == ["general"]


async def test_get_credential_capabilities_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
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
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                )
            },
            blocking=True,
            return_response=True,
        )


async def test_get_users(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_users returns user list."""
    api = _mock_access_control(lock_schlage_be469)

    user = MagicMock()
    user.user_id = 1
    user.user_name = "Alice"
    user.active = True
    user.user_type = UserCredentialUserType.GENERAL
    user.credential_rule = None
    api.async_get_users_cached.return_value = [user]
    api.async_get_all_credentials_cached.return_value = []
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_users",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[entity_id]["max_users"] == 20
    assert len(result[entity_id]["users"]) == 1
    assert result[entity_id]["users"][0]["user_index"] == 1
    assert result[entity_id]["users"][0]["user_name"] == "Alice"
    assert result[entity_id]["users"][0]["active"] is True


async def test_set_credential_auto_slot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with explicit user_index and auto-find slot."""
    api = _mock_access_control(lock_schlage_be469)

    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 10
    cred_caps = api.async_get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {UserCredentialType.PIN_CODE: pin_cap}

    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )
    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_index": 2,
            "credential_type": "pin_code",
            "credential_data": "1234",
        },
        blocking=True,
        return_response=True,
    )

    api.async_set_user.assert_not_called()
    api.async_set_credential.assert_called_once()
    assert result[entity_id]["user_index"] == 2
    assert result[entity_id]["credential_slot"] == 1


async def test_set_credential_explicit_slot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with explicit user_index and slot."""
    api = _mock_access_control(lock_schlage_be469)
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: entity_id,
            "credential_type": "pin_code",
            "credential_data": "5678",
            "user_index": 3,
            "credential_slot": 2,
        },
        blocking=True,
        return_response=True,
    )

    api.async_set_user.assert_not_called()
    api.async_set_credential.assert_called_once()
    assert result[entity_id]["user_index"] == 3
    assert result[entity_id]["credential_slot"] == 2


async def test_set_credential_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    lock_august_pro: Node,
    integration: MockConfigEntry,
) -> None:
    """set_credential across multiple devices returns per-device keyed result."""
    api1 = _mock_access_control(lock_schlage_be469)
    api2 = _mock_access_control(lock_august_pro)

    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 10
    for api in (api1, api2):
        cred_caps = api.async_get_credential_capabilities_cached.return_value
        cred_caps.supported_credential_types = {UserCredentialType.PIN_CODE: pin_cap}

    entity_1 = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )
    entity_2 = _lock_entity_id(
        entity_registry, device_registry, client, lock_august_pro
    )
    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: [entity_1, entity_2],
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_data": "1234",
        },
        blocking=True,
        return_response=True,
    )

    api1.async_set_credential.assert_called_once()
    api2.async_set_credential.assert_called_once()
    assert set(result.keys()) == {entity_1, entity_2}
    assert result[entity_1]["user_index"] == 1
    assert result[entity_2]["user_index"] == 1


async def test_set_credential_rejection_raises(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """A device-reported rejection must surface as HomeAssistantError."""
    api = _mock_access_control(lock_schlage_be469)
    api.async_set_credential = AsyncMock(
        return_value=SetCredentialResult.ERROR_DUPLICATE_CREDENTIAL
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_index": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
                "credential_slot": 1,
            },
            blocking=True,
            return_response=True,
        )


async def test_set_user_rejection_raises(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """A device-reported rejection on set_user must raise."""
    api = _mock_access_control(lock_schlage_be469)
    api.async_set_user = AsyncMock(
        return_value=SetUserResult.ERROR_ADD_REJECTED_LOCATION_OCCUPIED
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_user",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_index": 1,
                "user_name": "Guest",
            },
            blocking=True,
            return_response=True,
        )


async def test_set_credential_requires_user_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential rejects calls without user_index."""
    _mock_access_control(lock_schlage_be469)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "credential_type": "pin_code",
                "credential_data": "1234",
            },
            blocking=True,
            return_response=True,
        )


async def test_set_credential_type_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential fails when credential type is not supported (auto-slot)."""
    api = _mock_access_control(lock_schlage_be469)
    # Device reports no credential types supported
    cred_caps = api.async_get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_index": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
            },
            blocking=True,
            return_response=True,
        )


async def test_set_credential_no_available_slots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential fails when no credential slots free (auto-slot)."""
    api = _mock_access_control(lock_schlage_be469)

    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 2
    cred_caps = api.async_get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {UserCredentialType.PIN_CODE: pin_cap}

    # Fill all PIN slots
    cred1 = MagicMock()
    cred1.type = UserCredentialType.PIN_CODE
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = UserCredentialType.PIN_CODE
    cred2.slot = 2
    api.async_get_credentials_by_type_cached.return_value = [cred1, cred2]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_index": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
            },
            blocking=True,
            return_response=True,
        )


async def test_clear_credential(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_credential deletes a single credential."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "clear_credential",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 2,
        },
        blocking=True,
    )

    api.async_delete_credential.assert_called_once()


async def test_clear_all_credentials(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test clear_all_credentials deletes all credentials for a user."""
    api = _mock_access_control(lock_schlage_be469)

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
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_index": 1,
        },
        blocking=True,
    )

    assert api.async_delete_credential.call_count == 2


async def test_get_credential_status_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_status when credential exists."""
    api = _mock_access_control(lock_schlage_be469)

    cred = MagicMock()
    cred.user_id = 1
    api.async_get_credential_cached.return_value = cred
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_status",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result[entity_id]["credential_exists"] is True
    assert result[entity_id]["user_index"] == 1
    assert result[entity_id]["credential_type"] == "pin_code"
    assert result[entity_id]["credential_slot"] == 1


async def test_get_credential_status_not_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_status when credential does not exist."""
    api = _mock_access_control(lock_schlage_be469)
    api.async_get_credential_cached.return_value = None
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_credential_status",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_index": 1,
            "credential_type": "pin_code",
            "credential_slot": 5,
        },
        blocking=True,
        return_response=True,
    )

    assert result[entity_id]["credential_exists"] is False


@pytest.mark.parametrize("field", ["user_index", "credential_slot"])
@pytest.mark.parametrize("value", [0, 65536, 100000])
async def test_set_credential_id_range_validation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    field: str,
    value: int,
) -> None:
    """Reject user_index / credential_slot outside 1..65535."""
    _mock_access_control(lock_schlage_be469)

    payload: dict = {
        ATTR_ENTITY_ID: _lock_entity_id(
            entity_registry, device_registry, client, lock_schlage_be469
        ),
        "user_index": 1,
        "credential_type": "pin_code",
        "credential_data": "1234",
    }
    payload[field] = value

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            payload,
            blocking=True,
            return_response=True,
        )


async def test_clear_user_rejects_oversize_user_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Reject user_index above uint16 max on clear_user."""
    _mock_access_control(lock_schlage_be469)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "clear_user",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_index": 70000,
            },
            blocking=True,
        )


async def test_mutation_supports_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    lock_august_pro: Node,
    integration: MockConfigEntry,
) -> None:
    """clear_user across multiple devices dispatches to each node."""
    api1 = _mock_access_control(lock_schlage_be469)
    api2 = _mock_access_control(lock_august_pro)

    await hass.services.async_call(
        DOMAIN,
        "clear_user",
        {
            ATTR_ENTITY_ID: [
                _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                _lock_entity_id(
                    entity_registry, device_registry, client, lock_august_pro
                ),
            ],
            "user_index": 3,
        },
        blocking=True,
    )

    api1.async_delete_user.assert_called_once_with(3)
    api2.async_delete_user.assert_called_once_with(3)


async def test_get_users_supports_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469: Node,
    lock_august_pro: Node,
    integration: MockConfigEntry,
) -> None:
    """get_users returns a per-entity response when multiple locks are targeted."""
    api1 = _mock_access_control(lock_schlage_be469)
    api2 = _mock_access_control(lock_august_pro)

    user_1 = MagicMock()
    user_1.user_id = 1
    user_1.user_name = "Alice"
    user_1.active = True
    user_1.user_type = UserCredentialUserType.GENERAL
    user_1.credential_rule = None
    api1.async_get_users_cached.return_value = [user_1]

    user_2 = MagicMock()
    user_2.user_id = 2
    user_2.user_name = "Bob"
    user_2.active = True
    user_2.user_type = UserCredentialUserType.DISPOSABLE
    user_2.credential_rule = None
    api2.async_get_users_cached.return_value = [user_2]

    entity_1 = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )
    entity_2 = _lock_entity_id(
        entity_registry, device_registry, client, lock_august_pro
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_users",
        {ATTR_ENTITY_ID: [entity_1, entity_2]},
        blocking=True,
        return_response=True,
    )

    assert set(result) == {entity_1, entity_2}
    assert result[entity_1]["users"][0]["user_name"] == "Alice"
    assert result[entity_2]["users"][0]["user_name"] == "Bob"
