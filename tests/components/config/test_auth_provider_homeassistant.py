"""Test config entries API."""

from typing import Any

import pytest

from homeassistant.auth.providers import homeassistant as prov_ha
from homeassistant.components.config import auth_provider_homeassistant as auth_ha
from homeassistant.core import HomeAssistant

from tests.common import CLIENT_ID, MockUser
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_config(
    hass: HomeAssistant, local_auth: prov_ha.HassAuthProvider
) -> None:
    """Fixture that sets up the auth provider ."""
    auth_ha.async_setup(hass)


@pytest.fixture
async def auth_provider(
    local_auth: prov_ha.HassAuthProvider,
) -> prov_ha.HassAuthProvider:
    """Hass auth provider."""
    return local_auth


@pytest.fixture
async def owner_access_token(hass: HomeAssistant, hass_owner_user: MockUser) -> str:
    """Access token for owner user."""
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_owner_user, CLIENT_ID
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
async def hass_admin_credential(
    hass: HomeAssistant, auth_provider: prov_ha.HassAuthProvider
):
    """Overload credentials to admin user."""
    await hass.async_add_executor_job(
        auth_provider.data.add_auth, "test-user", "test-pass"
    )

    return await auth_provider.async_get_or_create_credentials(
        {"username": "test-user"}
    )


async def test_create_auth_system_generated_user(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can't add auth to system generated users."""
    system_user = MockUser(system_generated=True).add_to_hass(hass)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/create",
            "user_id": system_user.id,
            "username": "test-user",
            "password": "test-pass",
        }
    )

    result = await client.receive_json()

    assert not result["success"], result
    assert result["error"]["code"] == "system_generated"


async def test_create_auth_user_already_credentials() -> None:
    """Test we can't create auth for user with pre-existing credentials."""
    # assert False


async def test_create_auth_unknown_user(
    hass_ws_client: WebSocketGenerator, hass: HomeAssistant
) -> None:
    """Test create pointing at unknown user."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/create",
            "user_id": "test-id",
            "username": "test-user",
            "password": "test-pass",
        }
    )

    result = await client.receive_json()

    assert not result["success"], result
    assert result["error"]["code"] == "not_found"


async def test_create_auth_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test create requires admin to call API."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/create",
            "user_id": "test-id",
            "username": "test-user",
            "password": "test-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"


async def test_create_auth(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test create auth command works."""
    client = await hass_ws_client(hass)
    user = MockUser().add_to_hass(hass)

    assert len(user.credentials) == 0

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/create",
            "user_id": user.id,
            "username": "test-user2",
            "password": "test-pass",
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    assert len(user.credentials) == 1
    creds = user.credentials[0]
    assert creds.auth_provider_type == "homeassistant"
    assert creds.auth_provider_id is None
    assert creds.data == {"username": "test-user2"}
    assert prov_ha.STORAGE_KEY in hass_storage
    entry = hass_storage[prov_ha.STORAGE_KEY]["data"]["users"][1]
    assert entry["username"] == "test-user2"


async def test_create_auth_duplicate_username(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test we can't create auth with a duplicate username."""
    client = await hass_ws_client(hass)
    user = MockUser().add_to_hass(hass)

    hass_storage[prov_ha.STORAGE_KEY] = {
        "version": 1,
        "data": {"users": [{"username": "test-user"}]},
    }

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/create",
            "user_id": user.id,
            "username": "test-user",
            "password": "test-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"] == {
        "code": "home_assistant_error",
        "message": "username_already_exists",
        "translation_key": "username_already_exists",
        "translation_placeholders": {"username": "test-user"},
        "translation_domain": "auth",
    }


async def test_delete_removes_just_auth(
    hass_ws_client: WebSocketGenerator,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test deleting an auth without being connected to a user."""
    client = await hass_ws_client(hass)

    hass_storage[prov_ha.STORAGE_KEY] = {
        "version": 1,
        "data": {"users": [{"username": "test-user"}]},
    }

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/delete",
            "username": "test-user",
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    assert len(hass_storage[prov_ha.STORAGE_KEY]["data"]["users"]) == 0


async def test_delete_removes_credential(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test deleting auth that is connected to a user."""
    client = await hass_ws_client(hass)

    user = MockUser().add_to_hass(hass)
    hass_storage[prov_ha.STORAGE_KEY] = {
        "version": 1,
        "data": {"users": [{"username": "test-user"}]},
    }

    user.credentials.append(
        await hass.auth.auth_providers[0].async_get_or_create_credentials(
            {"username": "test-user"}
        )
    )

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/delete",
            "username": "test-user",
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    assert len(hass_storage[prov_ha.STORAGE_KEY]["data"]["users"]) == 0


async def test_delete_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test delete requires admin."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/delete",
            "username": "test-user",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"


async def test_delete_unknown_auth(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test trying to delete an unknown auth username."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/homeassistant/delete",
            "username": "test-user2",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"] == {
        "code": "home_assistant_error",
        "message": "user_not_found",
        "translation_key": "user_not_found",
        "translation_placeholders": None,
        "translation_domain": "auth",
    }


async def test_change_password(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: prov_ha.HassAuthProvider,
) -> None:
    """Test that change password succeeds with valid password."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/change_password",
            "current_password": "test-pass",
            "new_password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    await auth_provider.async_validate_login("test-user", "new-pass")


async def test_change_password_wrong_pw(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    auth_provider: prov_ha.HassAuthProvider,
) -> None:
    """Test that change password fails with invalid password."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/change_password",
            "current_password": "wrong-pass",
            "new_password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "invalid_current_password"
    with pytest.raises(prov_ha.InvalidAuth):
        await auth_provider.async_validate_login("test-user", "new-pass")


async def test_change_password_no_creds(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test that change password fails with no credentials."""
    hass_admin_user.credentials.clear()
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/change_password",
            "current_password": "test-pass",
            "new_password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "credentials_not_found"


async def test_admin_change_password_not_owner(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: prov_ha.HassAuthProvider,
) -> None:
    """Test that change password fails when not owner."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/admin_change_password",
            "user_id": "test-user",
            "password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"

    # Validate old login still works
    await auth_provider.async_validate_login("test-user", "test-pass")


async def test_admin_change_password_no_user(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, owner_access_token: str
) -> None:
    """Test that change password fails with unknown user."""
    client = await hass_ws_client(hass, owner_access_token)

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/admin_change_password",
            "user_id": "non-existing",
            "password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "user_not_found"


async def test_admin_change_password_no_cred(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    owner_access_token: str,
    hass_admin_user: MockUser,
) -> None:
    """Test that change password fails with unknown credential."""

    hass_admin_user.credentials.clear()
    client = await hass_ws_client(hass, owner_access_token)

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/admin_change_password",
            "user_id": hass_admin_user.id,
            "password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "credentials_not_found"


async def test_admin_change_password(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    owner_access_token: str,
    auth_provider: prov_ha.HassAuthProvider,
    hass_admin_user: MockUser,
) -> None:
    """Test that owners can change any password."""
    client = await hass_ws_client(hass, owner_access_token)

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/homeassistant/admin_change_password",
            "user_id": hass_admin_user.id,
            "password": "new-pass",
        }
    )

    result = await client.receive_json()
    assert result["success"], result

    await auth_provider.async_validate_login("test-user", "new-pass")


def _assert_username(
    local_auth: prov_ha.HassAuthProvider, username: str, *, should_exist: bool
) -> None:
    if any(user["username"] == username for user in local_auth.data.users):
        if should_exist:
            return  # found

        pytest.fail(f"Found user with username {username} when not expected")

    if should_exist:
        pytest.fail(f"Did not find user with username {username}")


async def _test_admin_change_username(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    local_auth: prov_ha.HassAuthProvider,
    hass_admin_user: MockUser,
    owner_access_token: str,
    new_username: str,
) -> dict[str, Any]:
    """Test admin change username ws endpoint."""
    client = await hass_ws_client(hass, owner_access_token)
    current_username_user = hass_admin_user.credentials[0].data["username"]
    _assert_username(local_auth, current_username_user, should_exist=True)

    await client.send_json_auto_id(
        {
            "type": "config/auth_provider/homeassistant/admin_change_username",
            "user_id": hass_admin_user.id,
            "username": new_username,
        }
    )
    return await client.receive_json()


async def test_admin_change_username_success(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    local_auth: prov_ha.HassAuthProvider,
    hass_admin_user: MockUser,
    owner_access_token: str,
) -> None:
    """Test that change username succeeds."""
    current_username = hass_admin_user.credentials[0].data["username"]
    new_username = "blabla"

    result = await _test_admin_change_username(
        hass,
        hass_ws_client,
        local_auth,
        hass_admin_user,
        owner_access_token,
        new_username,
    )

    assert result["success"], result
    _assert_username(local_auth, current_username, should_exist=False)
    _assert_username(local_auth, new_username, should_exist=True)
    assert hass_admin_user.credentials[0].data["username"] == new_username
    # Validate new login works
    await local_auth.async_validate_login(new_username, "test-pass")
    with pytest.raises(prov_ha.InvalidAuth):
        # Verify old login does not work
        await local_auth.async_validate_login(current_username, "test-pass")


@pytest.mark.parametrize("new_username", [" bla", "bla ", "BlA"])
async def test_admin_change_username_error_not_normalized(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    local_auth: prov_ha.HassAuthProvider,
    hass_admin_user: MockUser,
    owner_access_token: str,
    new_username: str,
) -> None:
    """Test that change username raises error."""
    current_username = hass_admin_user.credentials[0].data["username"]

    result = await _test_admin_change_username(
        hass,
        hass_ws_client,
        local_auth,
        hass_admin_user,
        owner_access_token,
        new_username,
    )
    assert not result["success"], result
    assert result["error"] == {
        "code": "home_assistant_error",
        "message": "username_not_normalized",
        "translation_key": "username_not_normalized",
        "translation_placeholders": {"new_username": new_username},
        "translation_domain": "auth",
    }
    _assert_username(local_auth, current_username, should_exist=True)
    _assert_username(local_auth, new_username, should_exist=False)
    assert hass_admin_user.credentials[0].data["username"] == current_username
    # Validate old login still works
    await local_auth.async_validate_login(current_username, "test-pass")


async def test_admin_change_username_not_owner(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, auth_provider
) -> None:
    """Test that change username fails when not owner."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "config/auth_provider/homeassistant/admin_change_username",
            "user_id": "test-user",
            "username": "new-user",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"

    # Validate old login still works
    await auth_provider.async_validate_login("test-user", "test-pass")


async def test_admin_change_username_no_user(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, owner_access_token
) -> None:
    """Test that change username fails with unknown user."""
    client = await hass_ws_client(hass, owner_access_token)

    await client.send_json_auto_id(
        {
            "type": "config/auth_provider/homeassistant/admin_change_username",
            "user_id": "non-existing",
            "username": "new-username",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "user_not_found"


async def test_admin_change_username_no_cred(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    owner_access_token,
    hass_admin_user: MockUser,
) -> None:
    """Test that change username fails with unknown credential."""

    hass_admin_user.credentials.clear()
    client = await hass_ws_client(hass, owner_access_token)

    await client.send_json_auto_id(
        {
            "type": "config/auth_provider/homeassistant/admin_change_username",
            "user_id": hass_admin_user.id,
            "username": "new-username",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "credentials_not_found"
