"""Test the habitica config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.habitica.const import (
    CONF_API_USER,
    DEFAULT_URL,
    DOMAIN,
    SECTION_REAUTH_API_KEY,
    SECTION_REAUTH_LOGIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ERROR_BAD_REQUEST, ERROR_NOT_AUTHORIZED

from tests.common import MockConfigEntry

TEST_API_USER = "a380546a-94be-4b8e-8a0b-23e0d5c03303"
TEST_API_KEY = "cd0e5985-17de-4b4f-849e-5d506c5e4382"


MOCK_DATA_LOGIN_STEP = {
    CONF_USERNAME: "test-email@example.com",
    CONF_PASSWORD: "test-password",
}
MOCK_DATA_ADVANCED_STEP = {
    CONF_API_USER: TEST_API_USER,
    CONF_API_KEY: TEST_API_KEY,
    CONF_URL: DEFAULT_URL,
    CONF_VERIFY_SSL: True,
}

USER_INPUT_REAUTH_LOGIN = {
    SECTION_REAUTH_LOGIN: {
        CONF_USERNAME: "new-email",
        CONF_PASSWORD: "new-password",
    },
    SECTION_REAUTH_API_KEY: {},
}
USER_INPUT_REAUTH_API_KEY = {
    SECTION_REAUTH_LOGIN: {},
    SECTION_REAUTH_API_KEY: {CONF_API_KEY: "cd0e5985-17de-4b4f-849e-5d506c5e4382"},
}


@pytest.mark.usefixtures("habitica")
async def test_form_login(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the login form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert "login" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "login"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "login"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LOGIN_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-user"
    assert result["data"] == {
        CONF_API_USER: TEST_API_USER,
        CONF_API_KEY: TEST_API_KEY,
        CONF_URL: DEFAULT_URL,
        CONF_NAME: "test-user",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == TEST_API_USER

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (ERROR_BAD_REQUEST, "cannot_connect"),
        (ERROR_NOT_AUTHORIZED, "invalid_auth"),
        (IndexError(), "unknown"),
    ],
)
async def test_form_login_errors(
    hass: HomeAssistant, habitica: AsyncMock, raise_error, text_error
) -> None:
    """Test we handle invalid credentials error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "login"}
    )

    habitica.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LOGIN_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    # recover from errors
    habitica.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LOGIN_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-user"
    assert result["data"] == {
        CONF_API_USER: TEST_API_USER,
        CONF_API_KEY: TEST_API_KEY,
        CONF_URL: DEFAULT_URL,
        CONF_NAME: "test-user",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == TEST_API_USER


@pytest.mark.usefixtures("habitica")
async def test_form_advanced(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert "advanced" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "advanced"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_ADVANCED_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-user"
    assert result["data"] == {
        CONF_API_USER: TEST_API_USER,
        CONF_API_KEY: TEST_API_KEY,
        CONF_URL: DEFAULT_URL,
        CONF_NAME: "test-user",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == TEST_API_USER

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (ERROR_BAD_REQUEST, "cannot_connect"),
        (ERROR_NOT_AUTHORIZED, "invalid_auth"),
        (IndexError(), "unknown"),
    ],
)
async def test_form_advanced_errors(
    hass: HomeAssistant, habitica: AsyncMock, raise_error, text_error
) -> None:
    """Test we handle invalid credentials error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )

    habitica.get_user.side_effect = raise_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_ADVANCED_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    # recover from errors
    habitica.get_user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_ADVANCED_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-user"
    assert result["data"] == {
        CONF_API_USER: TEST_API_USER,
        CONF_API_KEY: TEST_API_KEY,
        CONF_URL: DEFAULT_URL,
        CONF_NAME: "test-user",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == TEST_API_USER


@pytest.mark.usefixtures("habitica")
async def test_form_advanced_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort user data set when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_ADVANCED_STEP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "user_input",
    [
        (USER_INPUT_REAUTH_LOGIN),
        (USER_INPUT_REAUTH_API_KEY),
    ],
    ids=["reauth with login details", "rauth with api key"],
)
@pytest.mark.usefixtures("habitica")
async def test_flow_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, user_input: dict[str, Any]
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "cd0e5985-17de-4b4f-849e-5d506c5e4382"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "user_input", "text_error"),
    [
        (
            ERROR_BAD_REQUEST,
            USER_INPUT_REAUTH_LOGIN,
            "cannot_connect",
        ),
        (
            ERROR_NOT_AUTHORIZED,
            USER_INPUT_REAUTH_LOGIN,
            "invalid_auth",
        ),
        (IndexError(), USER_INPUT_REAUTH_LOGIN, "unknown"),
        (
            ERROR_BAD_REQUEST,
            USER_INPUT_REAUTH_API_KEY,
            "cannot_connect",
        ),
        (
            ERROR_NOT_AUTHORIZED,
            USER_INPUT_REAUTH_API_KEY,
            "invalid_auth",
        ),
        (IndexError(), USER_INPUT_REAUTH_API_KEY, "unknown"),
        (
            None,
            {SECTION_REAUTH_LOGIN: {}, SECTION_REAUTH_API_KEY: {}},
            "invalid_credentials",
        ),
    ],
    ids=[
        "login cannot_connect",
        "login invalid_auth",
        "login unknown",
        "api_key cannot_connect",
        "api_key invalid_auth",
        "api_key unknown",
        "invalid_credentials",
    ],
)
async def test_flow_reauth_errors(
    hass: HomeAssistant,
    habitica: AsyncMock,
    config_entry: MockConfigEntry,
    raise_error: Exception,
    user_input: dict[str, Any],
    text_error: str,
) -> None:
    """Test reauth flow with invalid credentials."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    habitica.get_user.side_effect = raise_error
    habitica.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    habitica.get_user.side_effect = None
    habitica.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT_REAUTH_API_KEY,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "cd0e5985-17de-4b4f-849e-5d506c5e4382"

    assert len(hass.config_entries.async_entries()) == 1
