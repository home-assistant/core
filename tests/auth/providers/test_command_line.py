"""Tests for the command_line auth provider."""

import os
from unittest.mock import AsyncMock
import uuid

import pytest

from homeassistant import data_entry_flow
from homeassistant.auth import AuthManager, auth_store, models as auth_models
from homeassistant.auth.providers import command_line
from homeassistant.const import CONF_TYPE


@pytest.fixture
async def store(hass):
    """Mock store."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    return store


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return command_line.CommandLineAuthProvider(
        hass,
        store,
        {
            CONF_TYPE: "command_line",
            command_line.CONF_COMMAND: os.path.join(
                os.path.dirname(__file__), "test_command_line_cmd.sh"
            ),
            command_line.CONF_ARGS: [],
            command_line.CONF_META: False,
        },
    )


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_create_new_credential(manager, provider) -> None:
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {"username": "good-user", "password": "good-pass"}
    )
    assert credentials.is_new is True

    user = await manager.async_get_or_create_user(credentials)
    assert user.is_active
    assert len(user.groups) == 1
    assert user.groups[0].id == "system-admin"
    assert not user.local_only


async def test_match_existing_credentials(store, provider) -> None:
    """See if we match existing users."""
    existing = auth_models.Credentials(
        id=uuid.uuid4(),
        auth_provider_type="command_line",
        auth_provider_id=None,
        data={"username": "good-user"},
        is_new=False,
    )
    provider.async_credentials = AsyncMock(return_value=[existing])
    credentials = await provider.async_get_or_create_credentials(
        {"username": "good-user", "password": "irrelevant"}
    )
    assert credentials is existing


async def test_invalid_username(provider) -> None:
    """Test we raise if incorrect user specified."""
    with pytest.raises(command_line.InvalidAuthError):
        await provider.async_validate_login("bad-user", "good-pass")


async def test_invalid_password(provider) -> None:
    """Test we raise if incorrect password specified."""
    with pytest.raises(command_line.InvalidAuthError):
        await provider.async_validate_login("good-user", "bad-pass")


async def test_good_auth(provider) -> None:
    """Test nothing is raised with good credentials."""
    await provider.async_validate_login("good-user", "good-pass")


async def test_good_auth_with_meta(manager, provider) -> None:
    """Test metadata is added upon successful authentication."""
    provider.config[command_line.CONF_ARGS] = ["--with-meta"]
    provider.config[command_line.CONF_META] = True

    await provider.async_validate_login("good-user", "good-pass")

    credentials = await provider.async_get_or_create_credentials(
        {"username": "good-user", "password": "good-pass"}
    )
    assert credentials.is_new is True

    user = await manager.async_get_or_create_user(credentials)
    assert user.name == "Bob"
    assert user.is_active
    assert len(user.groups) == 1
    assert user.groups[0].id == "system-users"
    assert user.local_only


async def test_utf_8_username_password(provider) -> None:
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {"username": "ßßß", "password": "äöü"}
    )
    assert credentials.is_new is True


async def test_login_flow_validates(provider) -> None:
    """Test login flow."""
    flow = await provider.async_login_flow({})
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await flow.async_step_init(
        {"username": "bad-user", "password": "bad-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await flow.async_step_init(
        {"username": "good-user", "password": "good-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "good-user"


async def test_strip_username(provider) -> None:
    """Test authentication works with username with whitespace around."""
    flow = await provider.async_login_flow({})
    result = await flow.async_step_init(
        {"username": "\t\ngood-user ", "password": "good-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "good-user"
