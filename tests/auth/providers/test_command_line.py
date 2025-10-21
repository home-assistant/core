"""Tests for the command_line auth provider."""

import os
from unittest.mock import AsyncMock
import uuid

import pytest

from homeassistant import data_entry_flow
from homeassistant.auth import AuthManager, auth_store, models as auth_models
from homeassistant.auth.providers import command_line
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant


@pytest.fixture
async def store(hass: HomeAssistant) -> auth_store.AuthStore:
    """Mock store."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    return store


@pytest.fixture
def provider(
    hass: HomeAssistant, store: auth_store.AuthStore
) -> command_line.CommandLineAuthProvider:
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
def manager(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    provider: command_line.CommandLineAuthProvider,
) -> AuthManager:
    """Mock manager."""
    return AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_create_new_credential(
    manager: AuthManager, provider: command_line.CommandLineAuthProvider
) -> None:
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


async def test_match_existing_credentials(
    provider: command_line.CommandLineAuthProvider,
) -> None:
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


async def test_invalid_username(provider: command_line.CommandLineAuthProvider) -> None:
    """Test we raise if incorrect user specified."""
    with pytest.raises(command_line.InvalidAuthError):
        await provider.async_validate_login("bad-user", "good-pass")


async def test_invalid_password(provider: command_line.CommandLineAuthProvider) -> None:
    """Test we raise if incorrect password specified."""
    with pytest.raises(command_line.InvalidAuthError):
        await provider.async_validate_login("good-user", "bad-pass")


async def test_good_auth(provider: command_line.CommandLineAuthProvider) -> None:
    """Test nothing is raised with good credentials."""
    await provider.async_validate_login("good-user", "good-pass")


async def test_good_auth_with_meta(
    manager: AuthManager, provider: command_line.CommandLineAuthProvider
) -> None:
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


async def test_utf_8_username_password(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {"username": "ßßß", "password": "äöü"}
    )
    assert credentials.is_new is True


async def test_login_flow_validates(
    provider: command_line.CommandLineAuthProvider,
) -> None:
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


async def test_strip_username(provider: command_line.CommandLineAuthProvider) -> None:
    """Test authentication works with username with whitespace around."""
    flow = await provider.async_login_flow({})
    result = await flow.async_step_init(
        {"username": "\t\ngood-user ", "password": "good-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "good-user"


async def test_async_run_auth_command_success(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _async_run_auth_command executes successfully with valid credentials."""
    env = {"username": "good-user", "password": "good-pass"}
    returncode, stdout = await provider._async_run_auth_command(env)
    
    assert returncode == 0
    assert stdout is None or isinstance(stdout, bytes)


async def test_async_run_auth_command_failure(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _async_run_auth_command returns non-zero exit code with invalid credentials."""
    env = {"username": "bad-user", "password": "bad-pass"}
    returncode, _ = await provider._async_run_auth_command(env)
    
    assert returncode != 0


async def test_async_run_auth_command_with_meta(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _async_run_auth_command captures stdout when meta is enabled."""
    provider.config[command_line.CONF_ARGS] = ["--with-meta"]
    provider.config[command_line.CONF_META] = True
    
    env = {"username": "good-user", "password": "good-pass"}
    returncode, stdout = await provider._async_run_auth_command(env)
    
    assert returncode == 0
    assert stdout is not None
    assert isinstance(stdout, bytes)
    assert len(stdout) > 0


async def test_async_run_auth_command_invalid_command(
    hass: HomeAssistant, store: auth_store.AuthStore
) -> None:
    """Test _async_run_auth_command raises InvalidAuthError for non-existent command."""
    provider = command_line.CommandLineAuthProvider(
        hass,
        store,
        {
            CONF_TYPE: "command_line",
            command_line.CONF_COMMAND: "/nonexistent/command",
            command_line.CONF_ARGS: [],
            command_line.CONF_META: False,
        },
    )
    
    env = {"username": "test", "password": "test"}
    with pytest.raises(command_line.InvalidAuthError):
        await provider._async_run_auth_command(env)


def test_parse_metadata_basic(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata parses valid key-value pairs."""
    stdout = b"name=Bob\ngroup=system-users\nlocal_only=true\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob",
        "group": "system-users",
        "local_only": "true",
    }


def test_parse_metadata_with_comments(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata ignores comment lines."""
    stdout = b"# This is a comment\nname=Alice\n# Another comment\ngroup=admin\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Alice",
        "group": "admin",
    }


def test_parse_metadata_with_whitespace(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata handles whitespace around keys and values."""
    stdout = b"  name = Bob Smith  \n  group =  system-users  \n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob Smith",
        "group": "system-users",
    }


def test_parse_metadata_filters_invalid_keys(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata only accepts allowed keys."""
    stdout = b"name=Bob\ninvalid_key=should_be_ignored\ngroup=users\nhacker=attack\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob",
        "group": "users",
    }
    assert "invalid_key" not in meta
    assert "hacker" not in meta


def test_parse_metadata_skips_malformed_lines(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata skips lines without equals sign."""
    stdout = b"name=Bob\nthis line has no equals\ngroup=users\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob",
        "group": "users",
    }


def test_parse_metadata_handles_empty_values(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata handles empty values correctly."""
    stdout = b"name=\ngroup=users\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "",
        "group": "users",
    }


def test_parse_metadata_handles_empty_output(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata returns empty dict for empty stdout."""
    stdout = b""
    meta = provider._parse_metadata(stdout)
    
    assert meta == {}


def test_parse_metadata_handles_invalid_utf8(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata handles invalid UTF-8 sequences gracefully."""
    stdout = b"name=Bob\n\xff\xfe invalid utf8 \n\ngroup=users\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob",
        "group": "users",
    }


def test_parse_metadata_with_equals_in_value(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata handles equals signs in values."""
    stdout = b"name=Bob=Smith=Jr\ngroup=users\n"
    meta = provider._parse_metadata(stdout)
    
    assert meta == {
        "name": "Bob=Smith=Jr",
        "group": "users",
    }


def test_parse_metadata_only_allowed_keys(
    provider: command_line.CommandLineAuthProvider,
) -> None:
    """Test _parse_metadata validates against ALLOWED_META_KEYS."""
    assert provider.ALLOWED_META_KEYS == ("name", "group", "local_only")
    
    stdout = b"name=Test\ngroup=admin\nlocal_only=true\n"
    meta = provider._parse_metadata(stdout)
    
    assert all(key in provider.ALLOWED_META_KEYS for key in meta.keys())
