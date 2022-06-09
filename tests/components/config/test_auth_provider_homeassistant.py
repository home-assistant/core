"""Test config entries API."""
import pytest

from homeassistant.auth.providers import homeassistant as prov_ha
from homeassistant.components.config import auth_provider_homeassistant as auth_ha

from tests.common import CLIENT_ID, MockUser


@pytest.fixture(autouse=True)
async def setup_config(hass, local_auth):
    """Fixture that sets up the auth provider ."""
    await auth_ha.async_setup(hass)


@pytest.fixture
async def auth_provider(local_auth):
    """Hass auth provider."""
    return local_auth


@pytest.fixture
async def owner_access_token(hass, hass_owner_user):
    """Access token for owner user."""
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_owner_user, CLIENT_ID
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
async def hass_admin_credential(hass, auth_provider):
    """Overload credentials to admin user."""
    await hass.async_add_executor_job(
        auth_provider.data.add_auth, "test-user", "test-pass"
    )

    return await auth_provider.async_get_or_create_credentials(
        {"username": "test-user"}
    )


async def test_create_auth_system_generated_user(hass, hass_ws_client):
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


async def test_create_auth_user_already_credentials():
    """Test we can't create auth for user with pre-existing credentials."""
    # assert False


async def test_create_auth_unknown_user(hass_ws_client, hass):
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
    hass, hass_ws_client, hass_read_only_access_token
):
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


async def test_create_auth(hass, hass_ws_client, hass_storage):
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


async def test_create_auth_duplicate_username(hass, hass_ws_client, hass_storage):
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
    assert result["error"]["code"] == "username_exists"


async def test_delete_removes_just_auth(hass_ws_client, hass, hass_storage):
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


async def test_delete_removes_credential(hass, hass_ws_client, hass_storage):
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


async def test_delete_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
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


async def test_delete_unknown_auth(hass, hass_ws_client):
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
    assert result["error"]["code"] == "auth_not_found"


async def test_change_password(hass, hass_ws_client, auth_provider):
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
    hass, hass_ws_client, hass_admin_user, auth_provider
):
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


async def test_change_password_no_creds(hass, hass_ws_client, hass_admin_user):
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


async def test_admin_change_password_not_owner(hass, hass_ws_client, auth_provider):
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


async def test_admin_change_password_no_user(hass, hass_ws_client, owner_access_token):
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
    hass, hass_ws_client, owner_access_token, hass_admin_user
):
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
    hass,
    hass_ws_client,
    owner_access_token,
    auth_provider,
    hass_admin_user,
):
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
