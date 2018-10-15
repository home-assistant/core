"""Tests for the auth store."""
from homeassistant.auth import auth_store


async def test_loading_old_data_format(hass, hass_storage):
    """Test we correctly load an old data format."""
    hass_storage[auth_store.STORAGE_KEY] = {
        'version': 1,
        'data': {
            'credentials': [],
            'users': [
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
                }
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
                    "user_id": "user-id"
                },
                {
                    "access_token_expiration": 1800.0,
                    "client_id": None,
                    "created_at": "2018-10-03T13:43:19.774637+00:00",
                    "id": "system-token-id",
                    "jwt_key": "some-key",
                    "last_used_at": "2018-10-03T13:43:19.774712+00:00",
                    "token": "some-token",
                    "user_id": "system-id"
                },
                {
                    "access_token_expiration": 1800.0,
                    "client_id": "http://localhost:8123/",
                    "created_at": "2018-10-03T13:43:19.774637+00:00",
                    "id": "hidden-because-no-jwt-id",
                    "last_used_at": "2018-10-03T13:43:19.774712+00:00",
                    "token": "some-token",
                    "user_id": "user-id"
                },
            ]
        }
    }

    store = auth_store.AuthStore(hass)
    groups = await store.async_get_groups()
    assert len(groups) == 1
    group = groups[0]
    assert group.name == "All Access"

    users = await store.async_get_users()
    assert len(users) == 2

    owner, system = users

    assert owner.system_generated is False
    assert owner.groups == [group]
    assert len(owner.refresh_tokens) == 1
    owner_token = list(owner.refresh_tokens.values())[0]
    assert owner_token.id == 'user-token-id'

    assert system.system_generated is True
    assert system.groups == []
    assert len(system.refresh_tokens) == 1
    system_token = list(system.refresh_tokens.values())[0]
    assert system_token.id == 'system-token-id'
