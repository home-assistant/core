"""Test the Home Assistant local auth provider."""

import asyncio
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config, auth_store
from homeassistant.auth.providers import (
    auth_provider_from_config,
    homeassistant as hass_auth,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def data(hass: HomeAssistant) -> hass_auth.Data:
    """Create a loaded data class."""
    data = hass_auth.Data(hass)
    await data.async_load()
    return data


@pytest.fixture
async def load_auth_component(hass: HomeAssistant) -> None:
    """Load the auth component for translations."""
    await async_setup_component(hass, "auth", {})


async def test_validating_password_invalid_user(data: hass_auth.Data) -> None:
    """Test validating an invalid user."""
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login("non-existing", "pw")


async def test_not_allow_set_id() -> None:
    """Test we are not allowed to set an ID in config."""
    hass = Mock()
    hass.data = {}
    with pytest.raises(vol.Invalid):
        await auth_provider_from_config(
            hass, None, {"type": "homeassistant", "id": "invalid"}
        )


async def test_new_users_populate_values(
    hass: HomeAssistant, data: hass_auth.Data
) -> None:
    """Test that we populate data for new users."""
    data.add_auth("hello", "test-pass")
    await data.async_save()

    manager = await auth_manager_from_config(hass, [{"type": "homeassistant"}], [])
    provider = manager.auth_providers[0]
    credentials = await provider.async_get_or_create_credentials({"username": "hello"})
    user = await manager.async_get_or_create_user(credentials)
    assert user.name == "hello"
    assert user.is_active


async def test_changing_password_raises_invalid_user(data: hass_auth.Data) -> None:
    """Test that changing password raises invalid user."""
    with pytest.raises(hass_auth.InvalidUser):
        data.change_password("non-existing", "pw")


# Modern mode


async def test_adding_user(data: hass_auth.Data) -> None:
    """Test adding a user."""
    data.add_auth("test-user", "test-pass")
    data.validate_login(" test-user ", "test-pass")


@pytest.mark.parametrize("username", ["test-user ", "TEST-USER"])
@pytest.mark.usefixtures("load_auth_component")
def test_adding_user_not_normalized(data: hass_auth.Data, username: str) -> None:
    """Test adding a user."""
    with pytest.raises(
        hass_auth.InvalidUsername, match=f'Username "{username}" is not normalized'
    ):
        data.add_auth(username, "test-pass")


@pytest.mark.usefixtures("load_auth_component")
def test_adding_user_duplicate_username(data: hass_auth.Data) -> None:
    """Test adding a user with duplicate username."""
    data.add_auth("test-user", "test-pass")

    with pytest.raises(
        hass_auth.InvalidUsername, match='Username "test-user" already exists'
    ):
        data.add_auth("test-user", "other-pass")


async def test_validating_password_invalid_password(data: hass_auth.Data) -> None:
    """Test validating an invalid password."""
    data.add_auth("test-user", "test-pass")

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login(" test-user ", "invalid-pass")

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login("test-user", "test-pass ")

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login("test-user", "Test-pass")


async def test_changing_password(data: hass_auth.Data) -> None:
    """Test adding a user."""
    data.add_auth("test-user", "test-pass")
    data.change_password("TEST-USER ", "new-pass")

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login("test-user", "test-pass")

    data.validate_login("test-UsEr", "new-pass")


async def test_password_truncated(data: hass_auth.Data) -> None:
    """Test long passwords are truncated before they are send to bcrypt for hashing.

    With bcrypt 5.0 passing a password longer than 72 bytes raises a ValueError.
    Previously the password was silently truncated.
    https://github.com/pyca/bcrypt/pull/1000
    """
    pwd_truncated = "hWwjDpFiYtDTaaMbXdjzeuKAPI3G4Di2mC92" * 4  # 72 chars
    long_pwd = pwd_truncated * 2  # 144 chars
    data.add_auth("test-user", long_pwd)
    data.validate_login("test-user", long_pwd)

    # As pwd are truncated, login will technically work with only the first 72 bytes.
    data.validate_login("test-user", pwd_truncated)
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login("test-user", pwd_truncated[:71])


async def test_login_flow_validates(data: hass_auth.Data, hass: HomeAssistant) -> None:
    """Test login flow."""
    data.add_auth("test-user", "test-pass")
    await data.async_save()

    provider = hass_auth.HassAuthProvider(
        hass, auth_store.AuthStore(hass), {"type": "homeassistant"}
    )
    flow = await provider.async_login_flow({})
    result = await flow.async_step_init()
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await flow.async_step_init(
        {"username": "incorrect-user", "password": "test-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await flow.async_step_init(
        {"username": "TEST-user ", "password": "incorrect-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await flow.async_step_init(
        {"username": "test-USER", "password": "test-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "test-USER"


async def test_saving_loading(data: hass_auth.Data, hass: HomeAssistant) -> None:
    """Test saving and loading JSON."""
    data.add_auth("test-user", "test-pass")
    data.add_auth("second-user", "second-pass")
    await data.async_save()

    data = hass_auth.Data(hass)
    await data.async_load()
    data.validate_login("test-user ", "test-pass")
    data.validate_login("second-user ", "second-pass")


async def test_get_or_create_credentials(
    hass: HomeAssistant, data: hass_auth.Data
) -> None:
    """Test that we can get or create credentials."""
    manager = await auth_manager_from_config(hass, [{"type": "homeassistant"}], [])
    provider = manager.auth_providers[0]
    provider.data = data
    credentials1 = await provider.async_get_or_create_credentials({"username": "hello"})
    with patch.object(provider, "async_credentials", return_value=[credentials1]):
        credentials2 = await provider.async_get_or_create_credentials(
            {"username": "hello "}
        )
    assert credentials1 is credentials2


async def test_race_condition_in_data_loading(hass: HomeAssistant) -> None:
    """Test race condition in the hass_auth.Data loading.

    Ref issue: https://github.com/home-assistant/core/issues/21569
    """
    counter = 0

    async def mock_load(_):
        """Mock of homeassistant.helpers.storage.Store.async_load."""
        nonlocal counter
        counter += 1
        await asyncio.sleep(0)

    provider = hass_auth.HassAuthProvider(
        hass, auth_store.AuthStore(hass), {"type": "homeassistant"}
    )
    with patch("homeassistant.helpers.storage.Store.async_load", new=mock_load):
        task1 = provider.async_validate_login("user", "pass")
        task2 = provider.async_validate_login("user", "pass")
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        assert counter == 1
        assert isinstance(results[0], hass_auth.InvalidAuth)
        # results[1] will be a TypeError if race condition occurred
        assert isinstance(results[1], hass_auth.InvalidAuth)


def test_change_username(data: hass_auth.Data) -> None:
    """Test changing username."""
    data.add_auth("test-user", "test-pass")
    users = data.users
    assert len(users) == 1
    assert users[0]["username"] == "test-user"

    data.change_username("test-user", "new-user")

    users = data.users
    assert len(users) == 1
    assert users[0]["username"] == "new-user"


def test_change_username_invalid_user(data: hass_auth.Data) -> None:
    """Test changing username raises on invalid user."""
    data.add_auth("test-user", "test-pass")
    users = data.users
    assert len(users) == 1
    assert users[0]["username"] == "test-user"

    with pytest.raises(hass_auth.InvalidUser):
        data.change_username("non-existing", "new-user")

    users = data.users
    assert len(users) == 1
    assert users[0]["username"] == "test-user"


@pytest.mark.usefixtures("load_auth_component")
async def test_change_username_not_normalized(
    data: hass_auth.Data, hass: HomeAssistant
) -> None:
    """Test changing username raises on not normalized username."""
    data.add_auth("test-user", "test-pass")

    with pytest.raises(
        hass_auth.InvalidUsername, match='Username "TEST-user " is not normalized'
    ):
        data.change_username("test-user", "TEST-user ")
