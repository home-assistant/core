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


# Policies only grant access, so cameras are hidden by not listing their domain.
NO_CAMERA_POLICY = {"entities": {"domains": {"light": True, "switch": True}}}


async def test_custom_group_crud_and_persistence(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test creating, updating, persisting and removing a custom group."""
    store = auth_store.AuthStore(hass)
    await store.async_load()

    group = await store.async_create_group("Guests", NO_CAMERA_POLICY)
    assert not group.system_generated
    user = await store.async_create_user("Guest", group_ids=[group.id])
    assert not user.permissions.check_entity("camera.front_door", "read")
    assert user.permissions.check_entity("light.kitchen", "read")

    # Policy changes take effect for existing members.
    await store.async_update_group(
        group, name="Visitors", policy={"entities": {"all": True}}
    )
    assert group.name == "Visitors"
    assert user.permissions.check_entity("camera.front_door", "read")

    await store.async_update_group(group, policy=NO_CAMERA_POLICY)
    hass_storage[auth_store.STORAGE_KEY] = {
        "version": auth_store.STORAGE_VERSION,
        "data": store._data_to_save(),
    }

    loaded_store = auth_store.AuthStore(hass)
    await loaded_store.async_load()
    loaded_group = await loaded_store.async_get_group(group.id)
    assert loaded_group is not None
    assert loaded_group.name == "Visitors"
    assert loaded_group.policy == NO_CAMERA_POLICY
    loaded_user = await loaded_store.async_get_user(user.id)
    assert loaded_user.groups == [loaded_group]
    assert not loaded_user.permissions.check_entity("camera.front_door", "read")

    await loaded_store.async_remove_group(loaded_group)
    assert await loaded_store.async_get_group(group.id) is None
    assert loaded_user.groups == []
    assert not loaded_user.permissions.check_entity("light.kitchen", "read")
    assert group.id not in [g["id"] for g in loaded_store._data_to_save()["groups"]]


@pytest.mark.parametrize(
    "group_id",
    [
        auth_store.GROUP_ID_ADMIN,
        auth_store.GROUP_ID_USER,
        auth_store.GROUP_ID_READ_ONLY,
    ],
)
async def test_system_groups_cannot_be_modified(
    hass: HomeAssistant, group_id: str
) -> None:
    """Test system groups cannot be updated or removed."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    group = await store.async_get_group(group_id)

    with pytest.raises(ValueError):
        await store.async_update_group(group, name="Hacked")
    with pytest.raises(ValueError):
        await store.async_remove_group(group)

    assert group.name != "Hacked"
    assert await store.async_get_group(group_id) is group
