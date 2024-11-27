"""Test the habitica config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.habitica.const import CONF_API_USER, DEFAULT_URL, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_DATA_LOGIN_STEP = {
    CONF_USERNAME: "test-email@example.com",
    CONF_PASSWORD: "test-password",
}
MOCK_DATA_ADVANCED_STEP = {
    CONF_API_USER: "test-api-user",
    CONF_API_KEY: "test-api-key",
    CONF_URL: DEFAULT_URL,
    CONF_VERIFY_SSL: True,
}

USER_INPUT_REAUTH_LOGIN = {
    "reauth_login": {
        CONF_USERNAME: "new-email",
        CONF_PASSWORD: "new-password",
    },
    "reauth_api_key": {},
}
USER_INPUT_REAUTH_API_KEY = {
    "reauth_login": {},
    "reauth_api_key": {CONF_API_KEY: "cd0e5985-17de-4b4f-849e-5d506c5e4382"},
}


async def test_form_login(hass: HomeAssistant) -> None:
    """Test we get the login form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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

    mock_obj = MagicMock()
    mock_obj.user.auth.local.login.post = AsyncMock()
    mock_obj.user.auth.local.login.post.return_value = {
        "id": "test-api-user",
        "apiToken": "test-api-key",
        "username": "test-username",
    }
    with (
        patch(
            "homeassistant.components.habitica.config_flow.HabitipyAsync",
            return_value=mock_obj,
        ),
        patch(
            "homeassistant.components.habitica.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.habitica.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_LOGIN_STEP,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        **MOCK_DATA_ADVANCED_STEP,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (ClientResponseError(MagicMock(), (), status=400), "cannot_connect"),
        (ClientResponseError(MagicMock(), (), status=401), "invalid_auth"),
        (IndexError(), "unknown"),
    ],
)
async def test_form_login_errors(hass: HomeAssistant, raise_error, text_error) -> None:
    """Test we handle invalid credentials error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "login"}
    )

    mock_obj = MagicMock()
    mock_obj.user.auth.local.login.post = AsyncMock(side_effect=raise_error)
    with patch(
        "homeassistant.components.habitica.config_flow.HabitipyAsync",
        return_value=mock_obj,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_LOGIN_STEP,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": text_error}


async def test_form_advanced(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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

    mock_obj = MagicMock()
    mock_obj.user.get = AsyncMock()
    mock_obj.user.get.return_value = {"auth": {"local": {"username": "test-username"}}}

    with (
        patch(
            "homeassistant.components.habitica.config_flow.HabitipyAsync",
            return_value=mock_obj,
        ),
        patch(
            "homeassistant.components.habitica.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.habitica.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_ADVANCED_STEP,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        **MOCK_DATA_ADVANCED_STEP,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (ClientResponseError(MagicMock(), (), status=400), "cannot_connect"),
        (ClientResponseError(MagicMock(), (), status=401), "invalid_auth"),
        (IndexError(), "unknown"),
    ],
)
async def test_form_advanced_errors(
    hass: HomeAssistant, raise_error, text_error
) -> None:
    """Test we handle invalid credentials error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )

    mock_obj = MagicMock()
    mock_obj.user.get = AsyncMock(side_effect=raise_error)

    with patch(
        "homeassistant.components.habitica.config_flow.HabitipyAsync",
        return_value=mock_obj,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_ADVANCED_STEP,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": text_error}


@pytest.mark.parametrize(
    "user_input",
    [
        (USER_INPUT_REAUTH_LOGIN),
        (USER_INPUT_REAUTH_API_KEY),
    ],
    ids=["reauth with login details", "rauth with api key"],
)
@pytest.mark.usefixtures("mock_habitica")
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
    assert config_entry.data == {
        "api_key": "cd0e5985-17de-4b4f-849e-5d506c5e4382",
        "api_user": "test-api-user",
        "url": "https://habitica.com",
    }

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_habitica")
async def test_flow_reauth_invalid_credentials(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with invalid credentials."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "reauth_login": {},
            "reauth_api_key": {},
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_credentials"}

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "user_input", "text_error"),
    [
        (
            ClientResponseError(MagicMock(), (), status=400),
            USER_INPUT_REAUTH_LOGIN,
            "cannot_connect",
        ),
        (
            ClientResponseError(MagicMock(), (), status=401),
            USER_INPUT_REAUTH_LOGIN,
            "invalid_auth",
        ),
        (IndexError(), USER_INPUT_REAUTH_LOGIN, "unknown"),
        (
            ClientResponseError(MagicMock(), (), status=400),
            USER_INPUT_REAUTH_API_KEY,
            "cannot_connect",
        ),
        (
            ClientResponseError(MagicMock(), (), status=401),
            USER_INPUT_REAUTH_API_KEY,
            "invalid_auth",
        ),
        (IndexError(), USER_INPUT_REAUTH_API_KEY, "unknown"),
        (None, {"reauth_login": {}, "reauth_api_key": {}}, "invalid_credentials"),
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

    mock_obj = MagicMock()
    mock_obj.user.get = AsyncMock(side_effect=raise_error)
    mock_obj.user.auth.local.login.post = AsyncMock(side_effect=raise_error)

    with patch(
        "homeassistant.components.habitica.config_flow.HabitipyAsync",
        return_value=mock_obj,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}
