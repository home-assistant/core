"""Tests for the Home Assistant auth module."""
from datetime import timedelta
import time
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import jwt
import pytest
import voluptuous as vol

from homeassistant import auth, data_entry_flow
from homeassistant.auth import (
    EVENT_USER_UPDATED,
    InvalidAuthError,
    auth_store,
    const as auth_const,
    models as auth_models,
)
from homeassistant.auth.const import GROUP_ID_ADMIN, MFA_SESSION_EXPIRATION
from homeassistant.auth.models import Credentials
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from tests.common import (
    CLIENT_ID,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    ensure_auth_manager_loaded,
    flush_store,
)


@pytest.fixture
def mock_hass(hass: HomeAssistant) -> HomeAssistant:
    """Home Assistant mock with minimum amount of data set to make it work with auth."""
    return hass


async def test_auth_manager_from_config_validates_config(mock_hass) -> None:
    """Test get auth providers."""
    with pytest.raises(vol.Invalid):
        manager = await auth.auth_manager_from_config(
            mock_hass,
            [
                {"name": "Test Name", "type": "insecure_example", "users": []},
                {
                    "name": "Invalid configuration because no users",
                    "type": "insecure_example",
                    "id": "invalid_config",
                },
            ],
            [],
        )

    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {"name": "Test Name", "type": "insecure_example", "users": []},
            {
                "name": "Test Name 2",
                "type": "insecure_example",
                "id": "another",
                "users": [],
            },
        ],
        [],
    )

    providers = [
        {"name": provider.name, "id": provider.id, "type": provider.type}
        for provider in manager.auth_providers
    ]

    assert providers == [
        {"name": "Test Name", "type": "insecure_example", "id": None},
        {"name": "Test Name 2", "type": "insecure_example", "id": "another"},
    ]


async def test_auth_manager_from_config_auth_modules(mock_hass) -> None:
    """Test get auth modules."""
    with pytest.raises(vol.Invalid):
        manager = await auth.auth_manager_from_config(
            mock_hass,
            [
                {"name": "Test Name", "type": "insecure_example", "users": []},
                {
                    "name": "Test Name 2",
                    "type": "insecure_example",
                    "id": "another",
                    "users": [],
                },
            ],
            [
                {"name": "Module 1", "type": "insecure_example", "data": []},
                {
                    "name": "Invalid configuration because no data",
                    "type": "insecure_example",
                    "id": "another",
                },
            ],
        )

    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {"name": "Test Name", "type": "insecure_example", "users": []},
            {
                "name": "Test Name 2",
                "type": "insecure_example",
                "id": "another",
                "users": [],
            },
        ],
        [
            {"name": "Module 1", "type": "insecure_example", "data": []},
            {
                "name": "Module 2",
                "type": "insecure_example",
                "id": "another",
                "data": [],
            },
        ],
    )
    providers = [
        {"name": provider.name, "type": provider.type, "id": provider.id}
        for provider in manager.auth_providers
    ]
    assert providers == [
        {"name": "Test Name", "type": "insecure_example", "id": None},
        {"name": "Test Name 2", "type": "insecure_example", "id": "another"},
    ]

    modules = [
        {"name": module.name, "type": module.type, "id": module.id}
        for module in manager.auth_mfa_modules
    ]
    assert modules == [
        {"name": "Module 1", "type": "insecure_example", "id": "insecure_example"},
        {"name": "Module 2", "type": "insecure_example", "id": "another"},
    ]


async def test_create_new_user(hass: HomeAssistant) -> None:
    """Test creating new user."""
    events = []

    @callback
    def user_added(event):
        events.append(event)

    hass.bus.async_listen("user_added", user_added)

    manager = await auth.auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [],
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    assert step["type"] == data_entry_flow.FlowResultType.FORM

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    credential = step["result"]
    assert credential is not None

    user = await manager.async_get_or_create_user(credential)
    assert user is not None
    assert user.is_owner is False
    assert user.name == "Test Name"

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["user_id"] == user.id


async def test_login_as_existing_user(mock_hass) -> None:
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [],
    )
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add a fake user that we're not going to log in with
    user = MockUser(
        id="mock-user2", is_owner=False, is_active=False, name="Not user"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id2",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "other-user"},
            is_new=False,
        )
    )

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        )
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    assert step["type"] == data_entry_flow.FlowResultType.FORM

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    credential = step["result"]
    user = await manager.async_get_user_by_credentials(credential)
    assert user is not None
    assert user.id == "mock-user"
    assert user.is_owner is False
    assert user.is_active is False
    assert user.name == "Paulus"


async def test_linking_user_to_two_auth_providers(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test linking user to two auth providers."""
    manager = await auth.auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            },
            {
                "type": "insecure_example",
                "id": "another-provider",
                "users": [{"username": "another-user", "password": "another-password"}],
            },
        ],
        [],
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    credential = step["result"]
    user = await manager.async_get_or_create_user(credential)
    assert user is not None

    step = await manager.login_flow.async_init(
        ("insecure_example", "another-provider"), context={"credential_only": True}
    )
    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "another-user", "password": "another-password"}
    )
    new_credential = step["result"]
    await manager.async_link_user(user, new_credential)
    assert len(user.credentials) == 2

    # Linking it again to same user is a no-op
    await manager.async_link_user(user, new_credential)
    assert len(user.credentials) == 2

    # Linking a credential to a user while the credential is already linked to another user should raise
    user_2 = await manager.async_create_user("User 2")
    with pytest.raises(ValueError):
        await manager.async_link_user(user_2, new_credential)
    assert len(user_2.credentials) == 0


async def test_saving_loading(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test storing and saving data.

    Creates one of each type that we store to test we restore correctly.
    """
    manager = await auth.auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [],
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    credential = step["result"]
    user = await manager.async_get_or_create_user(credential)

    await manager.async_activate_user(user)
    # the first refresh token will be used to create access token
    refresh_token = await manager.async_create_refresh_token(
        user, CLIENT_ID, credential=credential
    )
    manager.async_create_access_token(refresh_token, "192.168.0.1")
    # the second refresh token will not be used
    await manager.async_create_refresh_token(
        user, "dummy-client", credential=credential
    )

    await flush_store(manager._store._store)

    store2 = auth_store.AuthStore(hass)
    await store2.async_load()
    users = await store2.async_get_users()
    assert len(users) == 1
    assert users[0].permissions == user.permissions
    assert users[0] == user
    assert len(users[0].refresh_tokens) == 2
    for r_token in users[0].refresh_tokens.values():
        if r_token.client_id == CLIENT_ID:
            # verify the first refresh token
            assert r_token.last_used_at is not None
            assert r_token.last_used_ip == "192.168.0.1"
        elif r_token.client_id == "dummy-client":
            # verify the second refresh token
            assert r_token.last_used_at is None
            assert r_token.last_used_ip is None
        else:
            pytest.fail(f"Unknown client_id: {r_token.client_id}")


async def test_cannot_retrieve_expired_access_token(hass: HomeAssistant) -> None:
    """Test that we cannot retrieve expired access tokens."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
    assert refresh_token.user.id is user.id
    assert refresh_token.client_id == CLIENT_ID

    access_token = manager.async_create_access_token(refresh_token)
    assert manager.async_validate_access_token(access_token) is refresh_token

    # We patch time directly here because we want the access token to be created with
    # an expired time, but we do not want to freeze time so that jwt will compare it
    # to the patched time. If we freeze time for the test it will be frozen for jwt
    # as well and the token will not be expired.
    with patch(
        "homeassistant.auth.time.time",
        return_value=time.time()
        - auth_const.ACCESS_TOKEN_EXPIRATION.total_seconds()
        - 11,
    ):
        access_token = manager.async_create_access_token(refresh_token)

    assert manager.async_validate_access_token(access_token) is None


async def test_generating_system_user(hass: HomeAssistant) -> None:
    """Test that we can add a system user."""
    events = []

    @callback
    def user_added(event):
        events.append(event)

    hass.bus.async_listen("user_added", user_added)

    manager = await auth.auth_manager_from_config(hass, [], [])
    user = await manager.async_create_system_user("Hass.io")
    token = await manager.async_create_refresh_token(user)
    assert user.system_generated
    assert user.groups == []
    assert not user.local_only
    assert token is not None
    assert token.client_id is None
    assert token.token_type == auth.models.TOKEN_TYPE_SYSTEM
    assert token.expire_at is None

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["user_id"] == user.id

    # Passing arguments
    user = await manager.async_create_system_user(
        "Hass.io", group_ids=[GROUP_ID_ADMIN], local_only=True
    )
    token = await manager.async_create_refresh_token(user)
    assert user.system_generated
    assert user.is_admin
    assert user.local_only
    assert token is not None
    assert token.client_id is None
    assert token.token_type == auth.models.TOKEN_TYPE_SYSTEM
    assert token.expire_at is None

    await hass.async_block_till_done()
    assert len(events) == 2
    assert events[1].data["user_id"] == user.id


async def test_refresh_token_requires_client_for_user(hass: HomeAssistant) -> None:
    """Test create refresh token for a user with client_id."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    assert user.system_generated is False

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user)

    token = await manager.async_create_refresh_token(user, CLIENT_ID)
    assert token is not None
    assert token.client_id == CLIENT_ID
    assert token.token_type == auth_models.TOKEN_TYPE_NORMAL
    # default access token expiration
    assert token.access_token_expiration == auth_const.ACCESS_TOKEN_EXPIRATION


async def test_refresh_token_not_requires_client_for_system_user(
    hass: HomeAssistant,
) -> None:
    """Test create refresh token for a system user w/o client_id."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = await manager.async_create_system_user("Hass.io")
    assert user.system_generated is True

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user, CLIENT_ID)

    token = await manager.async_create_refresh_token(user)
    assert token is not None
    assert token.client_id is None
    assert token.token_type == auth_models.TOKEN_TYPE_SYSTEM


async def test_refresh_token_with_specific_access_token_expiration(
    hass: HomeAssistant,
) -> None:
    """Test create a refresh token with specific access token expiration."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)

    token = await manager.async_create_refresh_token(
        user, CLIENT_ID, access_token_expiration=timedelta(days=100)
    )
    assert token is not None
    assert token.client_id == CLIENT_ID
    assert token.access_token_expiration == timedelta(days=100)
    assert token.token_type == auth.models.TOKEN_TYPE_NORMAL
    assert token.expire_at is not None


async def test_refresh_token_type(hass: HomeAssistant) -> None:
    """Test create a refresh token with token type."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(
            user, CLIENT_ID, token_type=auth_models.TOKEN_TYPE_SYSTEM
        )

    token = await manager.async_create_refresh_token(
        user, CLIENT_ID, token_type=auth_models.TOKEN_TYPE_NORMAL
    )
    assert token is not None
    assert token.client_id == CLIENT_ID
    assert token.token_type == auth_models.TOKEN_TYPE_NORMAL


async def test_refresh_token_type_long_lived_access_token(hass: HomeAssistant) -> None:
    """Test create a refresh token has long-lived access token type."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(
            user, token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
        )

    token = await manager.async_create_refresh_token(
        user,
        client_name="GPS LOGGER",
        client_icon="mdi:home",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    )
    assert token is not None
    assert token.client_id is None
    assert token.client_name == "GPS LOGGER"
    assert token.client_icon == "mdi:home"
    assert token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    assert token.expire_at is None


async def test_refresh_token_provider_validation(mock_hass) -> None:
    """Test that creating access token from refresh token checks with provider."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [],
    )

    credential = auth_models.Credentials(
        id="mock-credential-id",
        auth_provider_type="insecure_example",
        auth_provider_id=None,
        data={"username": "test-user"},
        is_new=False,
    )

    user = MockUser().add_to_auth_manager(manager)
    user.credentials.append(credential)
    refresh_token = await manager.async_create_refresh_token(
        user, CLIENT_ID, credential=credential
    )
    ip = "127.0.0.1"

    assert manager.async_create_access_token(refresh_token, ip) is not None

    with patch(
        "homeassistant.auth.providers.insecure_example.ExampleAuthProvider.async_validate_refresh_token",
        side_effect=InvalidAuthError("Invalid access"),
    ) as call, pytest.raises(InvalidAuthError):
        manager.async_create_access_token(refresh_token, ip)

    call.assert_called_with(refresh_token, ip)


async def test_cannot_deactive_owner(mock_hass) -> None:
    """Test that we cannot deactivate the owner."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    owner = MockUser(is_owner=True).add_to_auth_manager(manager)

    with pytest.raises(ValueError):
        await manager.async_deactivate_user(owner)


async def test_remove_refresh_token(hass: HomeAssistant) -> None:
    """Test that we can remove a refresh token."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
    access_token = manager.async_create_access_token(refresh_token)

    manager.async_remove_refresh_token(refresh_token)

    assert manager.async_get_refresh_token(refresh_token.id) is None
    assert manager.async_validate_access_token(access_token) is None


async def test_remove_expired_refresh_token(hass: HomeAssistant) -> None:
    """Test that expired refresh tokens are deleted."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    now = dt_util.utcnow()
    with freeze_time(now):
        refresh_token1 = await manager.async_create_refresh_token(user, CLIENT_ID)
        assert (
            refresh_token1.expire_at
            == now.timestamp() + timedelta(days=90).total_seconds()
        )

    with freeze_time(now + timedelta(days=30)):
        async_fire_time_changed(hass, now + timedelta(days=30))
        refresh_token2 = await manager.async_create_refresh_token(user, CLIENT_ID)
        assert (
            refresh_token2.expire_at
            == now.timestamp() + timedelta(days=120).total_seconds()
        )

    with freeze_time(now + timedelta(days=89, hours=23)):
        async_fire_time_changed(hass, now + timedelta(days=89, hours=23))
        await hass.async_block_till_done()
        assert manager.async_get_refresh_token(refresh_token1.id)
        assert manager.async_get_refresh_token(refresh_token2.id)

    with freeze_time(now + timedelta(days=90, seconds=5)):
        async_fire_time_changed(hass, now + timedelta(days=90, seconds=5))
        await hass.async_block_till_done()
        assert manager.async_get_refresh_token(refresh_token1.id) is None
        assert manager.async_get_refresh_token(refresh_token2.id)

    with freeze_time(now + timedelta(days=120, seconds=5)):
        async_fire_time_changed(hass, now + timedelta(days=120, seconds=5))
        await hass.async_block_till_done()
        assert manager.async_get_refresh_token(refresh_token1.id) is None
        assert manager.async_get_refresh_token(refresh_token2.id) is None


async def test_update_expire_at_refresh_token(hass: HomeAssistant) -> None:
    """Test that expire at is updated when refresh token is used."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    now = dt_util.utcnow()
    with freeze_time(now):
        refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
        assert (
            refresh_token.expire_at
            == now.timestamp() + timedelta(days=90).total_seconds()
        )

    with freeze_time(now + timedelta(days=30)):
        async_fire_time_changed(hass, now + timedelta(days=30))
        await hass.async_block_till_done()
        assert manager.async_create_access_token(refresh_token)
        await hass.async_block_till_done()
        assert (
            refresh_token.expire_at
            == now.timestamp()
            + timedelta(days=30).total_seconds()
            + timedelta(days=90).total_seconds()
        )


async def test_register_revoke_token_callback(mock_hass) -> None:
    """Test that a registered revoke token callback is called."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)

    called = False

    def cb():
        nonlocal called
        called = True

    manager.async_register_revoke_token_callback(refresh_token.id, cb)
    manager.async_remove_refresh_token(refresh_token)
    assert called


async def test_unregister_revoke_token_callback(mock_hass) -> None:
    """Test that a revoke token callback can be unregistered."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)

    called = False

    def cb():
        nonlocal called
        called = True

    unregister = manager.async_register_revoke_token_callback(refresh_token.id, cb)
    unregister()

    manager.async_remove_refresh_token(refresh_token)
    assert not called


async def test_create_access_token(mock_hass) -> None:
    """Test normal refresh_token's jwt_key keep same after used."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_NORMAL
    jwt_key = refresh_token.jwt_key
    access_token = manager.async_create_access_token(refresh_token)
    assert access_token is not None
    assert refresh_token.jwt_key == jwt_key
    jwt_payload = jwt.decode(access_token, jwt_key, algorithms=["HS256"])
    assert jwt_payload["iss"] == refresh_token.id
    assert (
        jwt_payload["exp"] - jwt_payload["iat"] == timedelta(minutes=30).total_seconds()
    )


async def test_create_long_lived_access_token(mock_hass) -> None:
    """Test refresh_token's jwt_key changed for long-lived access token."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="GPS Logger",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=300),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)
    jwt_payload = jwt.decode(access_token, refresh_token.jwt_key, algorithms=["HS256"])
    assert jwt_payload["iss"] == refresh_token.id
    assert (
        jwt_payload["exp"] - jwt_payload["iat"] == timedelta(days=300).total_seconds()
    )


async def test_one_long_lived_access_token_per_refresh_token(mock_hass) -> None:
    """Test one refresh_token can only have one long-lived access token."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="GPS Logger",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)
    jwt_key = refresh_token.jwt_key

    rt = manager.async_validate_access_token(access_token)
    assert rt.id == refresh_token.id

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(
            user,
            client_name="GPS Logger",
            token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            access_token_expiration=timedelta(days=3000),
        )

    manager.async_remove_refresh_token(refresh_token)
    assert refresh_token.id not in user.refresh_tokens
    rt = manager.async_validate_access_token(access_token)
    assert rt is None, "Previous issued access token has been invoked"

    refresh_token_2 = await manager.async_create_refresh_token(
        user,
        client_name="GPS Logger",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token_2.id != refresh_token.id
    assert refresh_token_2.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token_2 = manager.async_create_access_token(refresh_token_2)
    jwt_key_2 = refresh_token_2.jwt_key

    assert access_token != access_token_2
    assert jwt_key != jwt_key_2

    rt = manager.async_validate_access_token(access_token_2)
    jwt_payload = jwt.decode(access_token_2, rt.jwt_key, algorithms=["HS256"])
    assert jwt_payload["iss"] == refresh_token_2.id
    assert (
        jwt_payload["exp"] - jwt_payload["iat"] == timedelta(days=3000).total_seconds()
    )


async def test_login_with_auth_module(mock_hass) -> None:
    """Test login as existing user with auth module."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [
            {
                "type": "insecure_example",
                "data": [{"user_id": "mock-user", "pin": "test-pin"}],
            }
        ],
    )
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        )
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    assert step["type"] == data_entry_flow.FlowResultType.FORM

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )

    # After auth_provider validated, request auth module input form
    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "mfa"

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"pin": "invalid-pin"}
    )

    # Invalid code error
    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "mfa"
    assert step["errors"] == {"base": "invalid_code"}

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"pin": "test-pin"}
    )

    # Finally passed, get credential
    assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert step["result"]
    assert step["result"].id == "mock-id"


async def test_login_with_multi_auth_module(mock_hass) -> None:
    """Test login as existing user with multiple auth modules."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [
            {
                "type": "insecure_example",
                "data": [{"user_id": "mock-user", "pin": "test-pin"}],
            },
            {
                "type": "insecure_example",
                "id": "module2",
                "data": [{"user_id": "mock-user", "pin": "test-pin2"}],
            },
        ],
    )
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        )
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    assert step["type"] == data_entry_flow.FlowResultType.FORM

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )

    # After auth_provider validated, request select auth module
    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "select_mfa_module"

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"multi_factor_auth_module": "module2"}
    )

    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "mfa"

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"pin": "test-pin2"}
    )

    # Finally passed, get credential
    assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert step["result"]
    assert step["result"].id == "mock-id"


async def test_auth_module_expired_session(mock_hass) -> None:
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [
            {
                "type": "insecure_example",
                "data": [{"user_id": "mock-user", "pin": "test-pin"}],
            }
        ],
    )
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        )
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    assert step["type"] == data_entry_flow.FlowResultType.FORM

    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )

    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "mfa"

    with freeze_time(dt_util.utcnow() + MFA_SESSION_EXPIRATION):
        step = await manager.login_flow.async_configure(
            step["flow_id"], {"pin": "test-pin"}
        )
        # login flow abort due session timeout
        assert step["type"] == data_entry_flow.FlowResultType.ABORT
        assert step["reason"] == "login_expired"


async def test_enable_mfa_for_user(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test enable mfa module for user."""
    manager = await auth.auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [{"type": "insecure_example", "data": []}],
    )

    step = await manager.login_flow.async_init(("insecure_example", None))
    step = await manager.login_flow.async_configure(
        step["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    credential = step["result"]
    user = await manager.async_get_or_create_user(credential)
    assert user is not None

    # new user don't have mfa enabled
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 0

    module = manager.get_auth_mfa_module("insecure_example")
    # mfa module don't have data
    assert bool(module._data) is False

    # test enable mfa for user
    await manager.async_enable_user_mfa(user, "insecure_example", {"pin": "test-pin"})
    assert len(module._data) == 1
    assert module._data[0] == {"user_id": user.id, "pin": "test-pin"}

    # test get enabled mfa
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 1
    assert "insecure_example" in modules

    # re-enable mfa for user will override
    await manager.async_enable_user_mfa(
        user, "insecure_example", {"pin": "test-pin-new"}
    )
    assert len(module._data) == 1
    assert module._data[0] == {"user_id": user.id, "pin": "test-pin-new"}
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 1
    assert "insecure_example" in modules

    # system user cannot enable mfa
    system_user = await manager.async_create_system_user("system-user")
    with pytest.raises(ValueError):
        await manager.async_enable_user_mfa(
            system_user, "insecure_example", {"pin": "test-pin"}
        )
    assert len(module._data) == 1
    modules = await manager.async_get_enabled_mfa(system_user)
    assert len(modules) == 0

    # disable mfa for user
    await manager.async_disable_user_mfa(user, "insecure_example")
    assert bool(module._data) is False

    # test get enabled mfa
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 0

    # disable mfa for user don't enabled just silent fail
    await manager.async_disable_user_mfa(user, "insecure_example")


async def test_async_remove_user(hass: HomeAssistant) -> None:
    """Test removing a user."""
    events = async_capture_events(hass, "user_removed")
    manager = await auth.auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        [],
    )
    hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(manager)
    user.credentials.append(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        )
    )
    assert len(user.credentials) == 1

    await hass.auth.async_remove_user(user)

    assert len(await manager.async_get_users()) == 0
    assert len(user.credentials) == 0

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["user_id"] == user.id


async def test_async_remove_user_fail_if_remove_credential_fails(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_admin_credential: Credentials
) -> None:
    """Test removing a user."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    with patch.object(
        hass.auth, "async_remove_credentials", side_effect=ValueError
    ), pytest.raises(ValueError):
        await hass.auth.async_remove_user(hass_admin_user)


async def test_new_users(mock_hass) -> None:
    """Test newly created users."""
    manager = await auth.auth_manager_from_config(
        mock_hass,
        [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    },
                    {
                        "username": "test-user-2",
                        "password": "test-pass",
                        "name": "Test Name",
                    },
                    {
                        "username": "test-user-3",
                        "password": "test-pass",
                        "name": "Test Name",
                    },
                ],
            }
        ],
        [],
    )
    ensure_auth_manager_loaded(manager)

    user = await manager.async_create_user("Hello")
    # first user in the system is owner and admin
    assert user.is_owner
    assert user.is_admin
    assert not user.local_only
    assert user.groups == []

    user = await manager.async_create_user("Hello 2")
    assert not user.is_admin
    assert user.groups == []

    user = await manager.async_create_user(
        "Hello 3", group_ids=["system-admin"], local_only=True
    )
    assert user.is_admin
    assert user.groups[0].id == "system-admin"
    assert user.local_only

    user_cred = await manager.async_get_or_create_user(
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=True,
        )
    )
    assert user_cred.is_admin


async def test_rename_does_not_change_refresh_token(mock_hass) -> None:
    """Test that we can rename without changing refresh token."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    await manager.async_create_refresh_token(user, CLIENT_ID)

    assert len(list(user.refresh_tokens.values())) == 1
    token_before = list(user.refresh_tokens.values())[0]

    await manager.async_update_user(user, name="new name")
    assert user.name == "new name"

    assert len(list(user.refresh_tokens.values())) == 1
    token_after = list(user.refresh_tokens.values())[0]

    assert token_before == token_after


async def test_event_user_updated_fires(hass: HomeAssistant) -> None:
    """Test the user updated event fires."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    await manager.async_create_refresh_token(user, CLIENT_ID)

    assert len(list(user.refresh_tokens.values())) == 1

    events = async_capture_events(hass, EVENT_USER_UPDATED)

    await manager.async_update_user(user, name="new name")
    assert user.name == "new name"

    await hass.async_block_till_done()
    assert len(events) == 1


async def test_access_token_with_invalid_signature(mock_hass) -> None:
    """Test rejecting access tokens with an invalid signature."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="Good Client",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)

    rt = manager.async_validate_access_token(access_token)
    assert rt.id == refresh_token.id

    # Now we corrupt the signature
    header, payload, signature = access_token.split(".")
    invalid_signature = "a" * len(signature)
    invalid_token = f"{header}.{payload}.{invalid_signature}"

    assert access_token != invalid_token

    result = manager.async_validate_access_token(invalid_token)
    assert result is None


async def test_access_token_with_null_signature(mock_hass) -> None:
    """Test rejecting access tokens with a null signature."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="Good Client",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)

    rt = manager.async_validate_access_token(access_token)
    assert rt.id == refresh_token.id

    # Now we make the signature all nulls
    header, payload, signature = access_token.split(".")
    invalid_signature = "\0" * len(signature)
    invalid_token = f"{header}.{payload}.{invalid_signature}"

    assert access_token != invalid_token

    result = manager.async_validate_access_token(invalid_token)
    assert result is None


async def test_access_token_with_empty_signature(mock_hass) -> None:
    """Test rejecting access tokens with an empty signature."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="Good Client",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)

    rt = manager.async_validate_access_token(access_token)
    assert rt.id == refresh_token.id

    # Now we make the signature all nulls
    header, payload, _ = access_token.split(".")
    invalid_token = f"{header}.{payload}."

    assert access_token != invalid_token

    result = manager.async_validate_access_token(invalid_token)
    assert result is None


async def test_access_token_with_empty_key(mock_hass) -> None:
    """Test rejecting access tokens with an empty key."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="Good Client",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3000),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN

    access_token = manager.async_create_access_token(refresh_token)

    manager.async_remove_refresh_token(refresh_token)
    # Now remove the token from the keyring
    # so we will get an empty key

    assert manager.async_validate_access_token(access_token) is None


async def test_reject_access_token_with_impossible_large_size(mock_hass) -> None:
    """Test rejecting access tokens with impossible sizes."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    assert manager.async_validate_access_token("a" * 10000) is None


async def test_reject_token_with_invalid_json_payload(mock_hass) -> None:
    """Test rejecting access tokens with invalid json payload."""
    jws = jwt.PyJWS()
    token_with_invalid_json = jws.encode(
        b"invalid", b"invalid", "HS256", {"alg": "HS256", "typ": "JWT"}
    )
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    assert manager.async_validate_access_token(token_with_invalid_json) is None


async def test_reject_token_with_not_dict_json_payload(mock_hass) -> None:
    """Test rejecting access tokens with not a dict json payload."""
    jws = jwt.PyJWS()
    token_not_a_dict_json = jws.encode(
        b'["invalid"]', b"invalid", "HS256", {"alg": "HS256", "typ": "JWT"}
    )
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    assert manager.async_validate_access_token(token_not_a_dict_json) is None


async def test_access_token_that_expires_soon(mock_hass) -> None:
    """Test access token from refresh token that expires very soon."""
    now = dt_util.utcnow()
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(
        user,
        client_name="Token that expires very soon",
        token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(seconds=1),
    )
    assert refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
    access_token = manager.async_create_access_token(refresh_token)

    rt = manager.async_validate_access_token(access_token)
    assert rt.id == refresh_token.id

    with freeze_time(now + timedelta(minutes=1)):
        assert manager.async_validate_access_token(access_token) is None


async def test_access_token_from_the_future(mock_hass) -> None:
    """Test we reject an access token from the future."""
    now = dt_util.utcnow()
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    with freeze_time(now + timedelta(days=365)):
        refresh_token = await manager.async_create_refresh_token(
            user,
            client_name="Token that expires very soon",
            token_type=auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            access_token_expiration=timedelta(days=10),
        )
        assert (
            refresh_token.token_type == auth_models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
        )
        access_token = manager.async_create_access_token(refresh_token)

    assert manager.async_validate_access_token(access_token) is None

    with freeze_time(now + timedelta(days=365)):
        rt = manager.async_validate_access_token(access_token)
        assert rt.id == refresh_token.id
