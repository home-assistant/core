"""Tests for the auth store."""
import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.auth import auth_store
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


async def test_loading_no_group_data_format(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly load old data without any groups."""
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
                    "group_ids": ["abcd-all-access"],
                },
                {
                    "id": "system-id",
                    "is_active": True,
                    "is_owner": True,
                    "name": "Hass.io",
                    "system_generated": True,
                },
            ],
            "groups": [{"id": "abcd-all-access", "name": "All Access"}],
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
                    "version": None,
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
    with patch(
        "homeassistant.helpers.entity_registry.async_get"
    ) as mock_ent_registry, patch(
        "homeassistant.helpers.device_registry.async_get"
    ) as mock_dev_registry, patch(
        "homeassistant.helpers.storage.Store.async_load", return_value=None
    ) as mock_load:
        await store.async_load()
        with pytest.raises(RuntimeError, match="Auth storage is already loaded"):
            await store.async_load()

        results = await asyncio.gather(store.async_get_users(), store.async_get_users())

        mock_ent_registry.assert_called_once_with(hass)
        mock_dev_registry.assert_called_once_with(hass)
        mock_load.assert_called_once_with()
        assert results[0] == results[1]


async def test_add_expire_at_property(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test we correctly add expired_at property if not existing."""
    now = dt_util.utcnow()
    with freeze_time(now):
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
                        "last_used_at": str(now - timedelta(days=10)),
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
                    },
                ],
            },
        }

        store = auth_store.AuthStore(hass)
        await store.async_load()

    users = await store.async_get_users()

    assert len(users[0].refresh_tokens) == 2
    token1, token2 = users[0].refresh_tokens.values()
    assert token1.expire_at
    assert token1.expire_at == now.timestamp() + timedelta(days=80).total_seconds()
    assert token2.expire_at
    assert token2.expire_at == now.timestamp() + timedelta(days=90).total_seconds()
