"""Tests for Z-Wave JS credential management services."""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest
import voluptuous as vol
from zwave_js_server.const.command_class.access_control import (
    SetCredentialResult,
    SetUserResult,
    UserCredentialType,
    UserCredentialUserType,
)
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.access_control import AccessControlAPI, SetUserOptions
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
    api = create_autospec(AccessControlAPI, instance=True)
    api.is_supported.return_value = True

    user_caps = MagicMock()
    user_caps.max_users = 20
    user_caps.supported_user_types = [UserCredentialUserType.GENERAL]
    user_caps.max_user_name_length = 20
    user_caps.supported_credential_rules = []
    api.get_user_capabilities_cached.return_value = user_caps

    pin_cap = MagicMock()
    pin_cap.number_of_credential_slots = 10
    pin_cap.min_credential_length = 4
    pin_cap.max_credential_length = 10
    pin_cap.supports_credential_learn = False

    password_cap = MagicMock()
    password_cap.number_of_credential_slots = 10
    password_cap.min_credential_length = 4
    password_cap.max_credential_length = 10
    password_cap.supports_credential_learn = False

    cred_caps = MagicMock()
    cred_caps.supported_credential_types = {
        UserCredentialType.PIN_CODE: pin_cap,
        UserCredentialType.PASSWORD: password_cap,
    }
    cred_caps.supports_admin_code = False
    cred_caps.supports_admin_code_deactivation = False
    api.get_credential_capabilities_cached.return_value = cred_caps

    api.get_users_cached.return_value = []
    api.get_user_cached.return_value = None
    api.set_user.return_value = SetUserResult.OK
    api.delete_user.return_value = SetUserResult.OK
    api.delete_all_users.return_value = SetUserResult.OK

    api.get_credentials_cached.return_value = []
    api.get_credentials_by_type_cached.return_value = []
    api.get_all_credentials_cached.return_value = []
    api.get_credential_cached.return_value = None
    api.set_credential.return_value = SetCredentialResult.OK
    api.delete_credential.return_value = SetCredentialResult.OK

    node.endpoints[0].access_control = api
    return api


def _device_id(
    device_registry: dr.DeviceRegistry, client: MagicMock, node: Node
) -> str:
    """Resolve the HA device_id for a mocked Z-Wave node."""
    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, node)}
    )
    assert device is not None
    return device.id


def _lock_entity_id(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
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
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user with auto-find user slot returns allocated user_id."""
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

    api.set_user.assert_called_once_with(
        1,
        SetUserOptions(
            active=True,
            user_type=UserCredentialUserType.GENERAL,
            user_name="Alice",
            credential_rule=None,
        ),
    )
    assert result == {entity_id: {"user_id": 1}}


async def test_set_user_explicit_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
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
            "user_id": 5,
            "user_name": "Bob",
        },
        blocking=True,
        return_response=True,
    )

    api.set_user.assert_called_once_with(
        5,
        SetUserOptions(
            active=None,
            user_type=None,
            user_name="Bob",
            credential_rule=None,
        ),
    )
    assert result == {entity_id: {"user_id": 5}}


async def test_set_user_no_slots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_user fails when no user slots available."""
    api = _mock_access_control(lock_schlage_be469)

    user_caps = api.get_user_capabilities_cached.return_value
    user_caps.max_users = 2
    user1 = MagicMock()
    user1.user_id = 1
    user2 = MagicMock()
    user2.user_id = 2
    api.get_users_cached.return_value = [user1, user2]

    with pytest.raises(HomeAssistantError) as exc:
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

    assert exc.value.translation_key == "no_available_user_slots"
    # Here, we fail trying to find a free user slot, meaning
    # before we even call set_user.
    api.set_user.assert_not_called()


async def test_delete_user(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test delete_user deletes a single user."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "delete_user",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_id": 3,
        },
        blocking=True,
    )

    api.delete_user.assert_called_once_with(3)


async def test_delete_all_users(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test delete_all_users deletes all users."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "delete_all_users",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
        },
        blocking=True,
    )

    api.delete_all_users.assert_called_once_with()


async def test_get_credential_capabilities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
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

    assert result == {
        entity_id: {
            "supports_user_management": True,
            "max_users": 20,
            "supported_user_types": ["general"],
            "max_user_name_length": 20,
            "supported_credential_rules": [],
            "supported_credential_types": {
                "pin_code": {
                    "num_slots": 10,
                    "min_length": 4,
                    "max_length": 10,
                    "supports_learn": False,
                },
                "password": {
                    "num_slots": 10,
                    "min_length": 4,
                    "max_length": 10,
                    "supports_learn": False,
                },
            },
        }
    }


async def test_get_credential_capabilities_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_credential_capabilities fails when not supported."""
    api = _mock_access_control(lock_schlage_be469)
    api.is_supported.return_value = False

    with pytest.raises(HomeAssistantError) as exc:
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

    assert exc.value.translation_key == "access_control_not_supported"
    # The call to is_supported tells us that access control is not supported
    # therefore we should not call the other methods, as they would throw.
    api.is_supported.assert_called_once_with()
    api.get_user_capabilities_cached.assert_not_called()
    api.get_credential_capabilities_cached.assert_not_called()


async def test_get_users(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test get_users returns user list without credential plaintext."""
    api = _mock_access_control(lock_schlage_be469)

    user = MagicMock()
    user.user_id = 1
    user.user_name = "Alice"
    user.active = True
    user.user_type = UserCredentialUserType.GENERAL
    user.credential_rule = None
    api.get_users_cached.return_value = [user]

    credential = MagicMock()
    credential.user_id = 1
    credential.type = UserCredentialType.PIN_CODE
    credential.slot = 3
    credential.data = "1234"
    api.get_all_credentials_cached.return_value = [credential]

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

    # Z-Wave can read back credential plaintext, but get_users must not expose it.
    # Assert the whole response so any extra field (especially `data`) trips the test.
    assert result == {
        entity_id: {
            "max_users": 20,
            "users": [
                {
                    "user_id": 1,
                    "user_name": "Alice",
                    "active": True,
                    "user_type": "general",
                    "credential_rule": None,
                    "credentials": [{"type": "pin_code", "slot": 3}],
                }
            ],
        }
    }


async def test_set_credential_auto_slot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with explicit user_id and auto-find slot."""
    api = _mock_access_control(lock_schlage_be469)

    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )
    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_id": 2,
            "credential_type": "pin_code",
            "credential_data": "1234",
        },
        blocking=True,
        return_response=True,
    )

    api.set_user.assert_not_called()
    api.set_credential.assert_called_once_with(
        2, UserCredentialType.PIN_CODE, 1, "1234"
    )
    assert result == {entity_id: {"user_id": 2, "credential_slot": 1}}


async def test_set_credential_explicit_slot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential with explicit user_id and slot."""
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
            "user_id": 3,
            "credential_slot": 2,
        },
        blocking=True,
        return_response=True,
    )

    api.set_user.assert_not_called()
    api.set_credential.assert_called_once_with(
        3, UserCredentialType.PIN_CODE, 2, "5678"
    )
    assert result == {entity_id: {"user_id": 3, "credential_slot": 2}}


async def test_set_credential_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    lock_august_pro: Node,
    integration: MockConfigEntry,
) -> None:
    """set_credential across multiple devices returns per-device keyed result."""
    api1 = _mock_access_control(lock_schlage_be469)
    api2 = _mock_access_control(lock_august_pro)

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
            "user_id": 1,
            "credential_type": "pin_code",
            "credential_data": "1234",
        },
        blocking=True,
        return_response=True,
    )

    api1.set_credential.assert_called_once_with(
        1, UserCredentialType.PIN_CODE, 1, "1234"
    )
    api2.set_credential.assert_called_once_with(
        1, UserCredentialType.PIN_CODE, 1, "1234"
    )
    assert result == {
        entity_1: {"user_id": 1, "credential_slot": 1},
        entity_2: {"user_id": 1, "credential_slot": 1},
    }


@pytest.mark.parametrize(
    ("set_user_result", "translation_key"),
    [
        (
            SetUserResult.ERROR_ADD_REJECTED_LOCATION_OCCUPIED,
            "user_rejected_add_occupied",
        ),
        (
            SetUserResult.ERROR_MODIFY_REJECTED_LOCATION_EMPTY,
            "user_rejected_modify_empty",
        ),
        (SetUserResult.ERROR_UNKNOWN, "user_rejected_unknown"),
    ],
)
async def test_set_user_rejection_raises(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    set_user_result: SetUserResult,
    translation_key: str,
) -> None:
    """A device-reported rejection on set_user must raise with a key per result."""
    api = _mock_access_control(lock_schlage_be469)
    api.set_user.return_value = set_user_result

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_user",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "user_name": "Guest",
            },
            blocking=True,
            return_response=True,
        )

    assert exc.value.translation_key == translation_key
    api.set_user.assert_called_once_with(
        1,
        SetUserOptions(
            active=None,
            user_type=None,
            user_name="Guest",
            credential_rule=None,
        ),
    )


@pytest.mark.parametrize(
    ("set_credential_result", "translation_key"),
    [
        (
            SetCredentialResult.ERROR_ADD_REJECTED_LOCATION_OCCUPIED,
            "credential_rejected_add_occupied",
        ),
        (
            SetCredentialResult.ERROR_MODIFY_REJECTED_LOCATION_EMPTY,
            "credential_rejected_modify_empty",
        ),
        # Z-Wave reports duplicate-admin-code separately, but we collapse it
        # to the generic duplicate key so the admin code is not leaked.
        (
            SetCredentialResult.ERROR_DUPLICATE_CREDENTIAL,
            "credential_rejected_duplicate",
        ),
        (
            SetCredentialResult.ERROR_DUPLICATE_ADMIN_PIN_CODE,
            "credential_rejected_duplicate",
        ),
        (
            SetCredentialResult.ERROR_MANUFACTURER_SECURITY_RULES,
            "credential_rejected_manufacturer_rules",
        ),
        (
            SetCredentialResult.ERROR_WRONG_USER_UNIQUE_IDENTIFIER,
            "credential_rejected_wrong_uuid",
        ),
        (SetCredentialResult.ERROR_UNKNOWN, "credential_rejected_unknown"),
    ],
)
async def test_set_credential_rejection_raises(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    set_credential_result: SetCredentialResult,
    translation_key: str,
) -> None:
    """A device-reported rejection on set_credential surfaces a key per result."""
    api = _mock_access_control(lock_schlage_be469)
    api.set_credential.return_value = set_credential_result

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
                "credential_slot": 1,
            },
            blocking=True,
            return_response=True,
        )

    assert exc.value.translation_key == translation_key
    api.set_credential.assert_called_once_with(
        1, UserCredentialType.PIN_CODE, 1, "1234"
    )


async def test_set_credential_requires_user_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential rejects calls without user_id."""
    api = _mock_access_control(lock_schlage_be469)

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

    # The schema rejects the missing user_id, so the helper is never reached
    # and no credential write is attempted on the device.
    api.set_credential.assert_not_called()


async def test_set_credential_type_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential fails when credential type is not supported (auto-slot)."""
    api = _mock_access_control(lock_schlage_be469)
    # Device reports no credential types supported
    cred_caps = api.get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types = {}

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
            },
            blocking=True,
            return_response=True,
        )

    # The device reports that pin_code is not in its supported set, so the
    # helper raises with the rendered credential type before any write.
    assert exc.value.translation_key == "credential_type_not_supported"
    assert exc.value.translation_placeholders == {"credential_type": "pin_code"}
    api.set_credential.assert_not_called()


async def test_set_credential_no_available_slots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test set_credential fails when no credential slots free (auto-slot)."""
    api = _mock_access_control(lock_schlage_be469)

    cred_caps = api.get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types[
        UserCredentialType.PIN_CODE
    ].number_of_credential_slots = 2

    # Fill all PIN slots
    cred1 = MagicMock()
    cred1.type = UserCredentialType.PIN_CODE
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = UserCredentialType.PIN_CODE
    cred2.slot = 2
    api.get_credentials_by_type_cached.return_value = [cred1, cred2]

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
            },
            blocking=True,
            return_response=True,
        )

    # Every pin_code slot the device reports is already taken, so auto-find
    # raises with the rendered credential type and nothing reaches the device.
    assert exc.value.translation_key == "no_available_credential_slots"
    assert exc.value.translation_placeholders == {"credential_type": "pin_code"}
    api.set_credential.assert_not_called()


@pytest.mark.parametrize(
    "credential_data",
    [
        "12ab",  # ASCII letters
        "١٢٣٤",  # Arabic-Indic digits — str.isdigit() returns True
        "１２３４",  # Fullwidth digits — str.isdigit() returns True
    ],
)
async def test_set_credential_pin_not_digits(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    credential_data: str,
) -> None:
    """PIN credential data must be ASCII 0-9, rejected locally otherwise."""
    api = _mock_access_control(lock_schlage_be469)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": credential_data,
                "credential_slot": 1,
            },
            blocking=True,
            return_response=True,
        )

    # PIN codes are validated locally to be ASCII-digits-only, so any other
    # value is rejected up front without bothering the device.
    assert exc.value.translation_key == "credential_data_pin_not_digits"
    api.set_credential.assert_not_called()


async def test_set_credential_password_allows_non_digits(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Password credentials must not be subject to the PIN-only digit check."""
    api = _mock_access_control(lock_schlage_be469)
    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_credential",
        {
            ATTR_ENTITY_ID: entity_id,
            "user_id": 1,
            "credential_type": "password",
            "credential_data": "s3cret!",
            "credential_slot": 1,
        },
        blocking=True,
        return_response=True,
    )

    api.set_credential.assert_called_once_with(
        1, UserCredentialType.PASSWORD, 1, "s3cret!"
    )
    assert result == {entity_id: {"user_id": 1, "credential_slot": 1}}


@pytest.mark.parametrize("credential_data", ["12", "12345678901"])
async def test_set_credential_length_validation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    credential_data: str,
) -> None:
    """Credential data outside the device-reported length range is rejected locally."""
    api = _mock_access_control(lock_schlage_be469)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": credential_data,
                "credential_slot": 1,
            },
            blocking=True,
            return_response=True,
        )

    # The helper compares the data length against the bounds the device
    # reported, so out-of-range values are caught locally and the device
    # is never asked to store an invalid credential.
    assert exc.value.translation_key == "credential_data_invalid_length"
    assert exc.value.translation_placeholders == {
        "credential_type": "pin_code",
        "min_length": "4",
        "max_length": "10",
    }
    api.set_credential.assert_not_called()


async def test_set_credential_slot_out_of_range(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Explicit credential_slot above device capacity fails fast."""
    api = _mock_access_control(lock_schlage_be469)
    cred_caps = api.get_credential_capabilities_cached.return_value
    cred_caps.supported_credential_types[
        UserCredentialType.PIN_CODE
    ].number_of_credential_slots = 5

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_credential",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
                "credential_slot": 6,
            },
            blocking=True,
            return_response=True,
        )

    # The explicit slot exceeds the device-reported capacity, so the helper
    # rejects the call with the rendered upper bound and never writes.
    assert exc.value.translation_key == "credential_slot_out_of_range"
    assert exc.value.translation_placeholders == {
        "credential_type": "pin_code",
        "max_slot": "5",
    }
    api.set_credential.assert_not_called()


async def test_delete_credential(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test delete_credential deletes a single credential."""
    api = _mock_access_control(lock_schlage_be469)

    await hass.services.async_call(
        DOMAIN,
        "delete_credential",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_id": 1,
            "credential_type": "pin_code",
            "credential_slot": 2,
        },
        blocking=True,
    )

    api.delete_credential.assert_called_once_with(1, UserCredentialType.PIN_CODE, 2)


async def test_delete_all_credentials(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Test delete_all_credentials deletes all credentials for a user."""
    api = _mock_access_control(lock_schlage_be469)

    cred1 = MagicMock()
    cred1.type = UserCredentialType.PIN_CODE
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = UserCredentialType.PIN_CODE
    cred2.slot = 2
    api.get_credentials_cached.return_value = [cred1, cred2]

    await hass.services.async_call(
        DOMAIN,
        "delete_all_credentials",
        {
            ATTR_ENTITY_ID: _lock_entity_id(
                entity_registry, device_registry, client, lock_schlage_be469
            ),
            "user_id": 1,
        },
        blocking=True,
    )

    assert api.delete_credential.call_count == 2
    api.delete_credential.assert_any_call(1, UserCredentialType.PIN_CODE, 1)
    api.delete_credential.assert_any_call(1, UserCredentialType.PIN_CODE, 2)


@pytest.mark.parametrize("field", ["user_id", "credential_slot"])
@pytest.mark.parametrize("value", [0, 65536, 100000])
async def test_set_credential_id_range_validation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    field: str,
    value: int,
) -> None:
    """Reject user_id / credential_slot outside 1..65535."""
    api = _mock_access_control(lock_schlage_be469)

    payload: dict = {
        ATTR_ENTITY_ID: _lock_entity_id(
            entity_registry, device_registry, client, lock_schlage_be469
        ),
        "user_id": 1,
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

    # The schema's uint16 range check fails on out-of-bounds ids, so the
    # call never reaches the helper and the device sees no write.
    api.set_credential.assert_not_called()


async def test_delete_user_rejects_oversize_user_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """Reject user_id above uint16 max on delete_user."""
    api = _mock_access_control(lock_schlage_be469)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "delete_user",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 70000,
            },
            blocking=True,
        )

    # The schema's uint16 range check rejects 70000 before the helper runs,
    # so no delete is dispatched to the device.
    api.delete_user.assert_not_called()


async def test_mutation_supports_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    lock_august_pro: Node,
    integration: MockConfigEntry,
) -> None:
    """delete_user across multiple devices dispatches to each node."""
    api1 = _mock_access_control(lock_schlage_be469)
    api2 = _mock_access_control(lock_august_pro)

    await hass.services.async_call(
        DOMAIN,
        "delete_user",
        {
            ATTR_ENTITY_ID: [
                _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                _lock_entity_id(
                    entity_registry, device_registry, client, lock_august_pro
                ),
            ],
            "user_id": 3,
        },
        blocking=True,
    )

    api1.delete_user.assert_called_once_with(3)
    api2.delete_user.assert_called_once_with(3)


async def test_get_users_supports_multi_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
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
    api1.get_users_cached.return_value = [user_1]

    user_2 = MagicMock()
    user_2.user_id = 2
    user_2.user_name = "Bob"
    user_2.active = True
    user_2.user_type = UserCredentialUserType.DISPOSABLE
    user_2.credential_rule = None
    api2.get_users_cached.return_value = [user_2]

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

    assert result == {
        entity_1: {
            "max_users": 20,
            "users": [
                {
                    "user_id": 1,
                    "user_name": "Alice",
                    "active": True,
                    "user_type": "general",
                    "credential_rule": None,
                    "credentials": [],
                }
            ],
        },
        entity_2: {
            "max_users": 20,
            "users": [
                {
                    "user_id": 2,
                    "user_name": "Bob",
                    "active": True,
                    "user_type": "disposable",
                    "credential_rule": None,
                    "credentials": [],
                }
            ],
        },
    }


@pytest.mark.parametrize(
    (
        "failing_attr",
        "service",
        "extra_payload",
        "returns_response",
        "translation_key",
        "placeholders",
    ),
    [
        (
            "set_user",
            "set_user",
            {"user_id": 1, "user_name": "Alice"},
            True,
            "set_user_failed",
            {},
        ),
        (
            "delete_user",
            "delete_user",
            {"user_id": 3},
            False,
            "delete_user_failed",
            {"user_id": "3"},
        ),
        (
            "delete_all_users",
            "delete_all_users",
            {},
            False,
            "delete_all_users_failed",
            {},
        ),
        (
            "get_user_capabilities_cached",
            "get_credential_capabilities",
            {},
            True,
            "get_credential_capabilities_failed",
            {},
        ),
        (
            "get_users_cached",
            "get_users",
            {},
            True,
            "get_users_failed",
            {},
        ),
        (
            "set_credential",
            "set_credential",
            {
                "user_id": 1,
                "credential_type": "pin_code",
                "credential_data": "1234",
                "credential_slot": 1,
            },
            True,
            "set_credential_failed",
            {},
        ),
        (
            "delete_credential",
            "delete_credential",
            {"user_id": 1, "credential_type": "pin_code", "credential_slot": 1},
            False,
            "delete_credential_failed",
            {},
        ),
    ],
)
async def test_server_error_wrapped_with_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    failing_attr: str,
    service: str,
    extra_payload: dict,
    returns_response: bool,
    translation_key: str,
    placeholders: dict,
) -> None:
    """zwave-js-server errors from helper calls surface a per-service translation key."""
    api = _mock_access_control(lock_schlage_be469)
    getattr(api, failing_attr).side_effect = FailedZWaveCommand("boom", 1, "boom")

    entity_id = _lock_entity_id(
        entity_registry, device_registry, client, lock_schlage_be469
    )

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **extra_payload},
            blocking=True,
            return_response=returns_response,
        )

    assert exc.value.translation_key == translation_key
    # The wrapper always renders the server error message; per-service
    # placeholders such as user_id must also be carried through.
    expected_placeholders = {
        "error": "zwave_error: Z-Wave error 1 - boom"
    } | placeholders
    assert exc.value.translation_placeholders == expected_placeholders


async def test_delete_all_credentials_failure_wrapped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """A server error during delete_all_credentials surfaces the wrap key."""
    api = _mock_access_control(lock_schlage_be469)

    cred = MagicMock()
    cred.type = UserCredentialType.PIN_CODE
    cred.slot = 1
    api.get_credentials_cached.return_value = [cred]
    api.delete_credential.side_effect = FailedZWaveCommand("boom", 1, "boom")

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "delete_all_credentials",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 7,
            },
            blocking=True,
        )

    assert exc.value.translation_key == "delete_all_credentials_failed"
    assert exc.value.translation_placeholders == {
        "error": "zwave_error: Z-Wave error 1 - boom",
        "user_id": "7",
    }


async def test_delete_all_credentials_partial_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Multiple delete_credential failures aggregate into a single error."""
    api = _mock_access_control(lock_schlage_be469)

    cred1 = MagicMock()
    cred1.type = UserCredentialType.PIN_CODE
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = UserCredentialType.PIN_CODE
    cred2.slot = 3
    cred3 = MagicMock()
    cred3.type = UserCredentialType.PIN_CODE
    cred3.slot = 5
    api.get_credentials_cached.return_value = [cred1, cred2, cred3]
    api.delete_credential.side_effect = [
        SetCredentialResult.OK,
        SetCredentialResult.ERROR_UNKNOWN,
        SetCredentialResult.ERROR_DUPLICATE_CREDENTIAL,
    ]

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "delete_all_credentials",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 7,
            },
            blocking=True,
        )

    assert exc.value.translation_key == "delete_all_credentials_partial_failure"
    assert exc.value.translation_placeholders == {
        "user_id": "7",
        "failed_count": "2",
    }
    assert "Failed to delete credential at slot 3 for user 7" in caplog.text
    assert "Failed to delete credential at slot 5 for user 7" in caplog.text


async def test_delete_all_credentials_single_failure_unwrapped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
) -> None:
    """A single rejection surfaces its specific translation key, not the aggregate one."""
    api = _mock_access_control(lock_schlage_be469)

    cred1 = MagicMock()
    cred1.type = UserCredentialType.PIN_CODE
    cred1.slot = 1
    cred2 = MagicMock()
    cred2.type = UserCredentialType.PIN_CODE
    cred2.slot = 2
    api.get_credentials_cached.return_value = [cred1, cred2]
    api.delete_credential.side_effect = [
        SetCredentialResult.OK,
        SetCredentialResult.ERROR_UNKNOWN,
    ]

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "delete_all_credentials",
            {
                ATTR_ENTITY_ID: _lock_entity_id(
                    entity_registry, device_registry, client, lock_schlage_be469
                ),
                "user_id": 7,
            },
            blocking=True,
        )

    assert exc.value.translation_key == "credential_rejected_unknown"
