"""Test config entries API."""
import pytest

from homeassistant.auth import models as auth_models
from homeassistant.components.config import auth as auth_config

from tests.common import CLIENT_ID, MockGroup, MockUser


@pytest.fixture(autouse=True)
def setup_config(hass, aiohttp_client):
    """Fixture that sets up the auth provider homeassistant module."""
    hass.loop.run_until_complete(auth_config.async_setup(hass))


async def test_list_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
    """Test get users requires auth."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json({"id": 5, "type": auth_config.WS_TYPE_LIST})

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"


async def test_list(hass, hass_ws_client, hass_admin_user):
    """Test get users."""
    group = MockGroup().add_to_hass(hass)

    owner = MockUser(
        id="abc", name="Test Owner", is_owner=True, groups=[group]
    ).add_to_hass(hass)

    owner.credentials.append(
        auth_models.Credentials(
            auth_provider_type="homeassistant",
            auth_provider_id=None,
            data={"username": "test-owner"},
        )
    )

    system = MockUser(id="efg", name="Test Hass.io", system_generated=True).add_to_hass(
        hass
    )

    inactive = MockUser(
        id="hij", name="Inactive User", is_active=False, groups=[group]
    ).add_to_hass(hass)

    refresh_token = await hass.auth.async_create_refresh_token(
        owner, CLIENT_ID, credential=owner.credentials[0]
    )
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json({"id": 5, "type": auth_config.WS_TYPE_LIST})

    result = await client.receive_json()
    assert result["success"], result
    data = result["result"]
    assert len(data) == 4
    assert data[0] == {
        "id": hass_admin_user.id,
        "username": "admin",
        "name": "Mock User",
        "is_owner": False,
        "is_active": True,
        "system_generated": False,
        "group_ids": [group.id for group in hass_admin_user.groups],
        "credentials": [{"type": "homeassistant"}],
    }
    assert data[1] == {
        "id": owner.id,
        "username": "test-owner",
        "name": "Test Owner",
        "is_owner": True,
        "is_active": True,
        "system_generated": False,
        "group_ids": [group.id for group in owner.groups],
        "credentials": [{"type": "homeassistant"}],
    }
    assert data[2] == {
        "id": system.id,
        "username": None,
        "name": "Test Hass.io",
        "is_owner": False,
        "is_active": True,
        "system_generated": True,
        "group_ids": [],
        "credentials": [],
    }
    assert data[3] == {
        "id": inactive.id,
        "username": None,
        "name": "Inactive User",
        "is_owner": False,
        "is_active": False,
        "system_generated": False,
        "group_ids": [group.id for group in inactive.groups],
        "credentials": [],
    }


async def test_delete_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
    """Test delete command requires an admin."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {"id": 5, "type": auth_config.WS_TYPE_DELETE, "user_id": "abcd"}
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"


async def test_delete_unable_self_account(hass, hass_ws_client, hass_access_token):
    """Test we cannot delete our own account."""
    client = await hass_ws_client(hass, hass_access_token)
    refresh_token = await hass.auth.async_validate_access_token(hass_access_token)

    await client.send_json(
        {"id": 5, "type": auth_config.WS_TYPE_DELETE, "user_id": refresh_token.user.id}
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "no_delete_self"


async def test_delete_unknown_user(hass, hass_ws_client, hass_access_token):
    """Test we cannot delete an unknown user."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json(
        {"id": 5, "type": auth_config.WS_TYPE_DELETE, "user_id": "abcd"}
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "not_found"


async def test_delete(hass, hass_ws_client, hass_access_token):
    """Test delete command works."""
    client = await hass_ws_client(hass, hass_access_token)
    test_user = MockUser(id="efg").add_to_hass(hass)

    assert len(await hass.auth.async_get_users()) == 2

    await client.send_json(
        {"id": 5, "type": auth_config.WS_TYPE_DELETE, "user_id": test_user.id}
    )

    result = await client.receive_json()
    assert result["success"], result
    assert len(await hass.auth.async_get_users()) == 1


async def test_create(hass, hass_ws_client, hass_access_token):
    """Test create command works."""
    client = await hass_ws_client(hass, hass_access_token)

    assert len(await hass.auth.async_get_users()) == 1

    await client.send_json({"id": 5, "type": "config/auth/create", "name": "Paulus"})

    result = await client.receive_json()
    assert result["success"], result
    assert len(await hass.auth.async_get_users()) == 2
    data_user = result["result"]["user"]
    user = await hass.auth.async_get_user(data_user["id"])
    assert user is not None
    assert user.name == data_user["name"]
    assert user.is_active
    assert user.groups == []
    assert not user.is_admin
    assert not user.is_owner
    assert not user.system_generated


async def test_create_user_group(hass, hass_ws_client, hass_access_token):
    """Test create user with a group."""
    client = await hass_ws_client(hass, hass_access_token)

    assert len(await hass.auth.async_get_users()) == 1

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth/create",
            "name": "Paulus",
            "group_ids": ["system-admin"],
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    assert len(await hass.auth.async_get_users()) == 2
    data_user = result["result"]["user"]
    user = await hass.auth.async_get_user(data_user["id"])
    assert user is not None
    assert user.name == data_user["name"]
    assert user.is_active
    assert user.groups[0].id == "system-admin"
    assert user.is_admin
    assert not user.is_owner
    assert not user.system_generated


async def test_create_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
    """Test create command requires an admin."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json({"id": 5, "type": "config/auth/create", "name": "YO"})

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"


async def test_update(hass, hass_ws_client):
    """Test update command works."""
    client = await hass_ws_client(hass)

    user = await hass.auth.async_create_user("Test user")

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth/update",
            "user_id": user.id,
            "name": "Updated name",
            "group_ids": ["system-read-only"],
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    data_user = result["result"]["user"]

    assert user.name == "Updated name"
    assert data_user["name"] == "Updated name"
    assert len(user.groups) == 1
    assert user.groups[0].id == "system-read-only"
    assert data_user["group_ids"] == ["system-read-only"]


async def test_update_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
    """Test update command requires an admin."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    user = await hass.auth.async_create_user("Test user")

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth/update",
            "user_id": user.id,
            "name": "Updated name",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "unauthorized"
    assert user.name == "Test user"


async def test_update_system_generated(hass, hass_ws_client):
    """Test update command cannot update a system generated."""
    client = await hass_ws_client(hass)

    user = await hass.auth.async_create_system_user("Test user")

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth/update",
            "user_id": user.id,
            "name": "Updated name",
        }
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "cannot_modify_system_generated"
    assert user.name == "Test user"


async def test_deactivate(hass, hass_ws_client):
    """Test deactivation and reactivation of regular user."""
    client = await hass_ws_client(hass)

    user = await hass.auth.async_create_user("Test user")
    assert user.is_active is True

    await client.send_json(
        {
            "id": 5,
            "type": "config/auth/update",
            "user_id": user.id,
            "name": "Updated name",
            "is_active": False,
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    data_user = result["result"]["user"]
    assert data_user["is_active"] is False

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth/update",
            "user_id": user.id,
            "name": "Updated name",
            "is_active": True,
        }
    )

    result = await client.receive_json()
    assert result["success"], result
    data_user = result["result"]["user"]
    assert data_user["is_active"] is True


async def test_deactivate_owner(hass, hass_ws_client):
    """Test that owner cannot be deactivated."""
    user = MockUser(id="abc", name="Test Owner", is_owner=True).add_to_hass(hass)

    assert user.is_active is True
    assert user.is_owner is True

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "config/auth/update", "user_id": user.id, "is_active": False}
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "cannot_deactivate_owner"


async def test_deactivate_system_generated(hass, hass_ws_client):
    """Test that owner cannot be deactivated."""
    client = await hass_ws_client(hass)

    user = await hass.auth.async_create_system_user("Test user")
    assert user.is_active is True
    assert user.system_generated is True
    assert user.is_owner is False

    await client.send_json(
        {"id": 5, "type": "config/auth/update", "user_id": user.id, "is_active": False}
    )

    result = await client.receive_json()
    assert not result["success"], result
    assert result["error"]["code"] == "cannot_modify_system_generated"
