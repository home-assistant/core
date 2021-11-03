"""Define tests for the SimpliSafe config flow."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simplipy.errors import InvalidCredentialsError, SimplipyError

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN
from homeassistant.components.simplisafe.config_flow import CONF_AUTH_CODE
from homeassistant.components.simplisafe.const import CONF_USER_ID
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="api")
def api_fixture():
    """Define a fixture for simplisafe-python API object."""
    api = Mock()
    api.refresh_token = "token123"
    api.user_id = "12345"
    return api


@pytest.fixture(name="mock_async_from_auth")
def mock_async_from_auth_fixture(api):
    """Define a fixture for simplipy.API.async_from_auth."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
    ) as mock_async_from_auth:
        mock_async_from_auth.side_effect = AsyncMock(return_value=api)
        yield mock_async_from_auth


async def test_duplicate_error(hass, mock_async_from_auth):
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_USER_ID: "12345",
            CONF_TOKEN: "token123",
        },
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_invalid_credentials(hass, mock_async_from_auth):
    """Test that invalid credentials show the correct error."""
    mock_async_from_auth.side_effect = AsyncMock(side_effect=InvalidCredentialsError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data={CONF_USER_ID: "12345", CONF_TOKEN: "token456"},
        options={CONF_CODE: "1234"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_CODE: "4321"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert entry.options == {CONF_CODE: "4321"}


async def test_step_reauth_old_format(hass, mock_async_from_auth):
    """Test the re-auth step with "old" config entries (those with user IDs)."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USER_ID: "12345", CONF_TOKEN: "token123"}


async def test_step_reauth_new_format(hass, mock_async_from_auth):
    """Test the re-auth step with "new" config entries (those with user IDs)."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_USER_ID: "12345",
            CONF_TOKEN: "token123",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USER_ID: "12345", CONF_TOKEN: "token123"},
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USER_ID: "12345", CONF_TOKEN: "token123"}


async def test_step_user(hass, mock_async_from_auth):
    """Test the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USER_ID: "12345", CONF_TOKEN: "token123"}


async def test_unknown_error(hass, mock_async_from_auth):
    """Test that an unknown error shows ohe correct error."""
    mock_async_from_auth.side_effect = AsyncMock(side_effect=SimplipyError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
