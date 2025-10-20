"""Tests for the auth store."""

import asyncio
from typing import Any
from unittest.mock import PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.auth import auth_store
from homeassistant.core import HomeAssistant

MOCK_STORAGE_DATA = {
    "version": 1,
    "data": {
        "credentials": [],
        "users": [
            {
                "id": "user-id",
                "is_active": True,
                "is_owner": True,
                "name": "Paulus",
                "system_generated": False,
            },
            {
                "id": "system-id",
                "is_active": True,
                "is_owner": True,
                "name": "Hass.io",
                "system_generated": True,
            },
        ],
        "refresh_tokens": [
            {
                "access_token_expiration": 1800.0,
                "client_id": "http://localhost:8123/",
                "created_at": "2018-10-03T13:43:19.774637+00:00",
                "id": "user-token-id",
                "jwt_key": "some-key",
                "last_used_at": "2018-10-03T13:43:19.774712+00:00",
                "token": "some-token",
                "user_id": "user-id",
                "version": "1.2.3",
            },
            {
                "access_token_expiration": 1800.0,
                "client_id": None,
                "created_at": "2018-10-03T13:43:19.774637+00:00",
                "id": "system-token-id",
                "jwt_key": "some-key",
                "last_used_at": "2018-10-03T13:43:19.774712+00:00",
                "token": "some-token",
                "user_id": "system-id",
            },
            {
                "access_token_expiration": 1800.0,
                "client_id": "http://localhost:8123/",
                "created_at": "2018-10-03T13:43:19.774637+00:00",
                "id": "hidden-because-no-jwt-id",
                "last_used_at": "2018-10-03T13:43:19.774712+00:00",
                "token": "some-token",
                "user_id": "user-id",
            },
        ],
    },
}


async def test_loading_no_group_data_format(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly load old data without any groups."""
    hass_storage[auth_store.STORAGE_KEY] = MOCK_STORAGE_DATA

    store = auth_store.AuthStore(hass)
    await store.async_load()
    groups = await store.async_get_groups()
    assert len(groups) == 3
    admin_group = groups[0]
    assert admin_group.name == auth_store.GROUP_NAME_ADMIN
    assert admin_group.system_generated
    assert admin_group.id == auth_store.GROUP_ID_ADMIN
    read_group = groups[1]
    assert read_group.name == auth_store.GROUP_NAME_READ_ONLY
    assert read_group.system_generated
    assert read_group.id == auth_store.GROUP_ID_READ_ONLY
    user_group = groups[2]
    assert user_group.name == auth_store.GROUP_NAME_USER
    assert user_group.system_generated
    assert user_group.id == auth_store.GROUP_ID_USER

    users = await store.async_get_users()
    assert len(users) == 2

    owner, system = users

    assert owner.system_generated is False
    assert owner.groups == [admin_group]
    assert len(owner.refresh_tokens) == 1
    owner_token = list(owner.refresh_tokens.values())[0]
    assert owner_token.id == "user-token-id"
    assert owner_token.version == "1.2.3"

    assert system.system_generated is True
    assert system.groups == []
    assert len(system.refresh_tokens) == 1
    system_token = list(system.refresh_tokens.values())[0]
    assert system_token.id == "system-token-id"
    assert system_token.version is None


async def test_loading_all_access_group_data_format(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly load old data with single group."""
    hass_storage[auth_store.STORAGE_KEY] = MOCK_STORAGE_DATA

    store = auth_store.AuthStore(hass)
    await store.async_load()
    groups = await store.async_get_groups()
    assert len(groups) == 3
    admin_group = groups[0]
    assert admin_group.name == auth_store.GROUP_NAME_ADMIN
    assert admin_group.system_generated
    assert admin_group.id == auth_store.GROUP_ID_ADMIN
    read_group = groups[1]
    assert read_group.name == auth_store.GROUP_NAME_READ_ONLY
    assert read_group.system_generated
    assert read_group.id == auth_store.GROUP_ID_READ_ONLY
    user_group = groups[2]
    assert user_group.name == auth_store.GROUP_NAME_USER
    assert user_group.system_generated
    assert user_group.id == auth_store.GROUP_ID_USER

    users = await store.async_get_users()
    assert len(users) == 2

    owner, system = users

    assert owner.system_generated is False
    assert owner.groups == [admin_group]
    assert len(owner.refresh_tokens) == 1
    owner_token = list(owner.refresh_tokens.values())[0]
    assert owner_token.id == "user-token-id"
    assert owner_token.version == "1.2.3"

    assert system.system_generated is True
    assert system.groups == []
    assert len(system.refresh_tokens) == 1
    system_token = list(system.refresh_tokens.values())[0]
    assert system_token.id == "system-token-id"
    assert system_token.version is None


async def test_loading_empty_data(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly load with no existing data."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    groups = await store.async_get_groups()
    assert len(groups) == 3
    admin_group = groups[0]
    assert admin_group.name == auth_store.GROUP_NAME_ADMIN
    assert admin_group.system_generated
    assert admin_group.id == auth_store.GROUP_ID_ADMIN
    user_group = groups[1]
    assert user_group.name == auth_store.GROUP_NAME_USER
    assert user_group.system_generated
    assert user_group.id == auth_store.GROUP_ID_USER
    read_group = groups[2]
    assert read_group.name == auth_store.GROUP_NAME_READ_ONLY
    assert read_group.system_generated
    assert read_group.id == auth_store.GROUP_ID_READ_ONLY

    users = await store.async_get_users()
    assert len(users) == 0


async def test_system_groups_store_id_and_name(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that for system groups we store the ID and name.

    Name is stored so that we remain backwards compat with < 0.82.
    """
    store = auth_store.AuthStore(hass)
    await store.async_load()
    data = store._data_to_save()
    assert len(data["users"]) == 0
    assert data["groups"] == [
        {"id": auth_store.GROUP_ID_ADMIN, "name": auth_store.GROUP_NAME_ADMIN},
        {"id": auth_store.GROUP_ID_USER, "name": auth_store.GROUP_NAME_USER},
        {"id": auth_store.GROUP_ID_READ_ONLY, "name": auth_store.GROUP_NAME_READ_ONLY},
    ]


async def test_loading_only_once(hass: HomeAssistant) -> None:
    """Test only one storage load is allowed."""
    store = auth_store.AuthStore(hass)
    with (
        patch("homeassistant.helpers.entity_registry.async_get") as mock_ent_registry,
        patch("homeassistant.helpers.device_registry.async_get") as mock_dev_registry,
        patch(
            "homeassistant.helpers.storage.Store.async_load", return_value=None
        ) as mock_load,
    ):
        await store.async_load()
        with pytest.raises(RuntimeError, match="Auth storage is already loaded"):
            await store.async_load()

        results = await asyncio.gather(store.async_get_users(), store.async_get_users())

        mock_ent_registry.assert_called_once_with(hass)
        mock_dev_registry.assert_called_once_with(hass)
        mock_load.assert_called_once_with()
        assert results[0] == results[1]


async def test_dont_change_expire_at_on_load(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly don't modify expired_at store load."""
    hass_storage[auth_store.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "credentials": [],
            "users": [
                {
                    "id": "user-id",
                    "is_active": True,
                    "is_owner": True,
                    "name": "Paulus",
                    "system_generated": False,
                },
                {
                    "id": "system-id",
                    "is_active": True,
                    "is_owner": True,
                    "name": "Hass.io",
                    "system_generated": True,
                },
            ],
            "refresh_tokens": [
                {
                    "access_token_expiration": 1800.0,
                    "client_id": "http://localhost:8123/",
                    "created_at": "2018-10-03T13:43:19.774637+00:00",
                    "id": "user-token-id",
                    "jwt_key": "some-key",
                    "token": "some-token",
                    "user_id": "user-id",
                    "version": "1.2.3",
                },
                {
                    "access_token_expiration": 1800.0,
                    "client_id": "http://localhost:8123/",
                    "created_at": "2018-10-03T13:43:19.774637+00:00",
                    "id": "user-token-id2",
                    "jwt_key": "some-key2",
                    "token": "some-token",
                    "user_id": "user-id",
                    "expire_at": 1724133771.079745,
                },
            ],
        },
    }

    store = auth_store.AuthStore(hass)
    await store.async_load()

    users = await store.async_get_users()

    assert len(users[0].refresh_tokens) == 2
    token1, token2 = users[0].refresh_tokens.values()
    assert not token1.expire_at
    assert token2.expire_at == 1724133771.079745


async def test_loading_does_not_write_right_away(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Test after calling load we wait five minutes to write."""
    hass_storage[auth_store.STORAGE_KEY] = MOCK_STORAGE_DATA

    store = auth_store.AuthStore(hass)
    await store.async_load()

    # Wipe storage so we can verify if it was written
    hass_storage[auth_store.STORAGE_KEY] = {}

    freezer.tick(auth_store.DEFAULT_SAVE_DELAY)
    await hass.async_block_till_done()
    assert hass_storage[auth_store.STORAGE_KEY] == {}
    freezer.tick(auth_store.INITIAL_LOAD_SAVE_DELAY)
    # Once for scheduling the task
    await hass.async_block_till_done()
    # Once for the task
    await hass.async_block_till_done()
    assert hass_storage[auth_store.STORAGE_KEY] != {}


async def test_duplicate_uuid(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we don't override user if we have a duplicate user ID."""
    hass_storage[auth_store.STORAGE_KEY] = MOCK_STORAGE_DATA
    store = auth_store.AuthStore(hass)
    await store.async_load()
    with patch("uuid.UUID.hex", new_callable=PropertyMock) as hex_mock:
        hex_mock.side_effect = ["user-id", "new-id"]
        user = await store.async_create_user("Test User")
    assert len(hex_mock.mock_calls) == 2
    assert user.id == "new-id"


async def test_add_remove_user_affects_tokens(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test adding and removing a user removes the tokens."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    user = await store.async_create_user("Test User")
    assert user.name == "Test User"
    refresh_token = await store.async_create_refresh_token(
        user, "client_id", "access_token_expiration"
    )
    assert user.refresh_tokens == {refresh_token.id: refresh_token}
    assert await store.async_get_user(user.id) == user
    assert store.async_get_refresh_token(refresh_token.id) == refresh_token
    assert store.async_get_refresh_token_by_token(refresh_token.token) == refresh_token
    await store.async_remove_user(user)
    assert store.async_get_refresh_token(refresh_token.id) is None
    assert store.async_get_refresh_token_by_token(refresh_token.token) is None
    assert user.refresh_tokens == {}


async def test_set_expiry_date(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Test set expiry date of a refresh token."""
    hass_storage[auth_store.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "credentials": [],
            "users": [
                {
                    "id": "user-id",
                    "is_active": True,
                    "is_owner": True,
                    "name": "Paulus",
                    "system_generated": False,
                },
            ],
            "refresh_tokens": [
                {
                    "access_token_expiration": 1800.0,
                    "client_id": "http://localhost:8123/",
                    "created_at": "2018-10-03T13:43:19.774637+00:00",
                    "id": "user-token-id",
                    "jwt_key": "some-key",
                    "token": "some-token",
                    "user_id": "user-id",
                    "expire_at": 1724133771.079745,
                },
            ],
        },
    }

    store = auth_store.AuthStore(hass)
    await store.async_load()

    users = await store.async_get_users()

    assert len(users[0].refresh_tokens) == 1
    (token,) = users[0].refresh_tokens.values()
    assert token.expire_at == 1724133771.079745

    store.async_set_expiry(token, enable_expiry=False)
    assert token.expire_at is None

    freezer.tick(auth_store.DEFAULT_SAVE_DELAY * 2)
    # Once for scheduling the task
    await hass.async_block_till_done()
    # Once for the task
    await hass.async_block_till_done()

    # verify token is saved without expire_at
    assert (
        hass_storage[auth_store.STORAGE_KEY]["data"]["refresh_tokens"][0]["expire_at"]
        is None
    )

    store.async_set_expiry(token, enable_expiry=True)
    assert token.expire_at is not None


def test_load_groups_with_system_groups(hass: HomeAssistant) -> None:
    """Test _load_groups creates system groups correctly."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    data = {
        "groups": [
            {"id": auth_store.GROUP_ID_ADMIN, "name": "Administrators"},
            {"id": auth_store.GROUP_ID_USER, "name": "Users"},
        ]
    }
    
    groups, group_without_policy, migrate_users = store._load_groups(data)
    
    assert len(groups) == 3  # Admin, User, and Read Only
    assert auth_store.GROUP_ID_ADMIN in groups
    assert auth_store.GROUP_ID_USER in groups
    assert auth_store.GROUP_ID_READ_ONLY in groups
    assert group_without_policy is None
    assert migrate_users is False
    
    # Verify system groups have correct properties
    admin_group = groups[auth_store.GROUP_ID_ADMIN]
    assert admin_group.system_generated is True
    assert admin_group.name == auth_store.GROUP_NAME_ADMIN


def test_load_groups_with_empty_data(hass: HomeAssistant) -> None:
    """Test _load_groups with no groups data."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    data = {}
    
    groups, group_without_policy, migrate_users = store._load_groups(data)
    
    # Should create all 3 system groups
    assert len(groups) == 3
    assert auth_store.GROUP_ID_ADMIN in groups
    assert auth_store.GROUP_ID_USER in groups
    assert auth_store.GROUP_ID_READ_ONLY in groups
    assert group_without_policy is None
    assert migrate_users is True  # Should migrate users when no groups exist


def test_load_groups_with_custom_group(hass: HomeAssistant) -> None:
    """Test _load_groups with custom group that has a policy."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    custom_policy = {"entities": {"domains": {"light": True}}}
    data = {
        "groups": [
            {
                "id": "custom-group-id",
                "name": "Custom Group",
                "policy": custom_policy,
            }
        ]
    }
    
    groups, group_without_policy, migrate_users = store._load_groups(data)
    
    # Should have custom group plus 3 system groups
    assert len(groups) == 4
    assert "custom-group-id" in groups
    assert groups["custom-group-id"].name == "Custom Group"
    assert groups["custom-group-id"].policy == custom_policy
    assert groups["custom-group-id"].system_generated is False
    assert group_without_policy is None
    assert migrate_users is False


def test_load_groups_with_group_without_policy(hass: HomeAssistant) -> None:
    """Test _load_groups with custom group without policy (should be skipped)."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    data = {
        "groups": [
            {
                "id": "no-policy-group",
                "name": "Group Without Policy",
            }
        ]
    }
    
    groups, group_without_policy, migrate_users = store._load_groups(data)
    
    # Group without policy should be skipped, only system groups created
    assert len(groups) == 3
    assert "no-policy-group" not in groups
    assert group_without_policy == "no-policy-group"
    assert migrate_users is False


def test_load_users_basic(hass: HomeAssistant) -> None:
    """Test _load_users loads users correctly."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create groups first
    groups = {
        auth_store.GROUP_ID_ADMIN: auth_store._system_admin_group(),
        auth_store.GROUP_ID_USER: auth_store._system_user_group(),
    }
    
    data = {
        "users": [
            {
                "id": "test-user-id",
                "name": "Test User",
                "is_owner": False,
                "is_active": True,
                "system_generated": False,
                "group_ids": [auth_store.GROUP_ID_USER],
            }
        ]
    }
    
    users = store._load_users(data, groups, perm_lookup, None, False)
    
    assert len(users) == 1
    assert "test-user-id" in users
    user = users["test-user-id"]
    assert user.name == "Test User"
    assert user.is_owner is False
    assert user.is_active is True
    assert user.system_generated is False
    assert len(user.groups) == 1
    assert user.groups[0].id == auth_store.GROUP_ID_USER


def test_load_users_with_migration(hass: HomeAssistant) -> None:
    """Test _load_users migrates users to admin group when needed."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    groups = {
        auth_store.GROUP_ID_ADMIN: auth_store._system_admin_group(),
    }
    
    data = {
        "users": [
            {
                "id": "test-user-id",
                "name": "Test User",
                "is_owner": True,
                "is_active": True,
                "system_generated": False,
                "group_ids": [],
            }
        ]
    }
    
    users = store._load_users(data, groups, perm_lookup, None, True)
    
    assert len(users) == 1
    user = users["test-user-id"]
    # Non-system user should be migrated to admin group
    assert len(user.groups) == 1
    assert user.groups[0].id == auth_store.GROUP_ID_ADMIN


def test_load_users_system_user_no_migration(hass: HomeAssistant) -> None:
    """Test _load_users doesn't migrate system-generated users."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    groups = {
        auth_store.GROUP_ID_ADMIN: auth_store._system_admin_group(),
    }
    
    data = {
        "users": [
            {
                "id": "system-user-id",
                "name": "System User",
                "is_owner": False,
                "is_active": True,
                "system_generated": True,
                "group_ids": [],
            }
        ]
    }
    
    users = store._load_users(data, groups, perm_lookup, None, True)
    
    assert len(users) == 1
    user = users["system-user-id"]
    # System user should NOT be migrated
    assert len(user.groups) == 0


def test_load_credentials_basic(hass: HomeAssistant) -> None:
    """Test _load_credentials loads credentials correctly."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create a user
    users = {
        "test-user-id": models.User(
            id="test-user-id",
            name="Test User",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        )
    }
    
    data = {
        "credentials": [
            {
                "id": "cred-id-1",
                "user_id": "test-user-id",
                "auth_provider_type": "homeassistant",
                "auth_provider_id": None,
                "data": {"username": "testuser"},
            }
        ]
    }
    
    credentials = store._load_credentials(data, users)
    
    assert len(credentials) == 1
    assert "cred-id-1" in credentials
    cred = credentials["cred-id-1"]
    assert cred.id == "cred-id-1"
    assert cred.auth_provider_type == "homeassistant"
    assert cred.data == {"username": "testuser"}
    assert cred.is_new is False
    
    # Verify credential was added to user
    assert len(users["test-user-id"].credentials) == 1
    assert users["test-user-id"].credentials[0] == cred


def test_load_credentials_multiple_users(hass: HomeAssistant) -> None:
    """Test _load_credentials with multiple users and credentials."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create multiple users
    users = {
        "user-1": models.User(
            id="user-1",
            name="User 1",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        ),
        "user-2": models.User(
            id="user-2",
            name="User 2",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        ),
    }
    
    data = {
        "credentials": [
            {
                "id": "cred-1",
                "user_id": "user-1",
                "auth_provider_type": "homeassistant",
                "auth_provider_id": None,
                "data": {"username": "user1"},
            },
            {
                "id": "cred-2",
                "user_id": "user-1",
                "auth_provider_type": "google",
                "auth_provider_id": None,
                "data": {"email": "user1@example.com"},
            },
            {
                "id": "cred-3",
                "user_id": "user-2",
                "auth_provider_type": "homeassistant",
                "auth_provider_id": None,
                "data": {"username": "user2"},
            },
        ]
    }
    
    credentials = store._load_credentials(data, users)
    
    assert len(credentials) == 3
    assert len(users["user-1"].credentials) == 2
    assert len(users["user-2"].credentials) == 1


def test_load_refresh_tokens_basic(hass: HomeAssistant) -> None:
    """Test _load_refresh_tokens loads tokens correctly."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create a user
    users = {
        "test-user-id": models.User(
            id="test-user-id",
            name="Test User",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        )
    }
    
    credentials = {}
    
    data = {
        "refresh_tokens": [
            {
                "id": "token-id-1",
                "user_id": "test-user-id",
                "client_id": "http://localhost:8123/",
                "created_at": "2024-10-21T13:43:19.774637+00:00",
                "access_token_expiration": 1800.0,
                "token": "test-token",
                "jwt_key": "test-jwt-key",
                "last_used_at": "2024-10-21T14:00:00.000000+00:00",
                "last_used_ip": "192.168.1.1",
            }
        ]
    }
    
    store._load_refresh_tokens(data, users, credentials)
    
    assert len(users["test-user-id"].refresh_tokens) == 1
    token = list(users["test-user-id"].refresh_tokens.values())[0]
    assert token.id == "token-id-1"
    assert token.client_id == "http://localhost:8123/"
    assert token.token == "test-token"
    assert token.jwt_key == "test-jwt-key"
    assert token.last_used_ip == "192.168.1.1"
    assert token.token_type == models.TOKEN_TYPE_NORMAL


def test_load_refresh_tokens_with_credential(hass: HomeAssistant) -> None:
    """Test _load_refresh_tokens associates credentials correctly."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create a user
    users = {
        "test-user-id": models.User(
            id="test-user-id",
            name="Test User",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        )
    }
    
    # Create a credential
    cred = models.Credentials(
        id="cred-id-1",
        is_new=False,
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "testuser"},
    )
    credentials = {"cred-id-1": cred}
    
    data = {
        "refresh_tokens": [
            {
                "id": "token-id-1",
                "user_id": "test-user-id",
                "client_id": "http://localhost:8123/",
                "created_at": "2024-10-21T13:43:19.774637+00:00",
                "access_token_expiration": 1800.0,
                "token": "test-token",
                "jwt_key": "test-jwt-key",
                "credential_id": "cred-id-1",
            }
        ]
    }
    
    store._load_refresh_tokens(data, users, credentials)
    
    assert len(users["test-user-id"].refresh_tokens) == 1
    token = list(users["test-user-id"].refresh_tokens.values())[0]
    assert token.credential == cred


def test_load_refresh_tokens_skips_invalid_created_at(
    hass: HomeAssistant,
) -> None:
    """Test _load_refresh_tokens skips tokens with invalid created_at."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create a user
    users = {
        "test-user-id": models.User(
            id="test-user-id",
            name="Test User",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        )
    }
    
    credentials = {}
    
    data = {
        "refresh_tokens": [
            {
                "id": "token-id-1",
                "user_id": "test-user-id",
                "client_id": "http://localhost:8123/",
                "created_at": "invalid-date",
                "access_token_expiration": 1800.0,
                "token": "test-token",
                "jwt_key": "test-jwt-key",
            }
        ]
    }
    
    store._load_refresh_tokens(data, users, credentials)
    
    # Token should be skipped due to invalid created_at
    assert len(users["test-user-id"].refresh_tokens) == 0


def test_load_refresh_tokens_skips_missing_jwt_key(hass: HomeAssistant) -> None:
    """Test _load_refresh_tokens skips tokens without jwt_key."""
    store = auth_store.AuthStore(hass)
    store._loaded = True
    
    from homeassistant.auth.permissions.models import PermissionLookup
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.auth import models
    
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    perm_lookup = PermissionLookup(ent_reg, dev_reg)
    
    # Create a user
    users = {
        "test-user-id": models.User(
            id="test-user-id",
            name="Test User",
            is_owner=False,
            is_active=True,
            system_generated=False,
            groups=[],
            perm_lookup=perm_lookup,
        )
    }
    
    credentials = {}
    
    data = {
        "refresh_tokens": [
            {
                "id": "token-id-1",
                "user_id": "test-user-id",
                "client_id": "http://localhost:8123/",
                "created_at": "2024-10-21T13:43:19.774637+00:00",
                "access_token_expiration": 1800.0,
                "token": "test-token",
                # jwt_key is missing
            }
        ]
    }
    
    store._load_refresh_tokens(data, users, credentials)
    
    # Token should be skipped due to missing jwt_key
    assert len(users["test-user-id"].refresh_tokens) == 0
