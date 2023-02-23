"""Test Roborock config flow."""
from unittest.mock import patch

from roborock.exceptions import RoborockException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.roborock.const import CONF_ENTRY_CODE, DOMAIN
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .mock_data import MOCK_CONFIG, USER_EMAIL


async def test_successful_config_flow(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Check that user form requesting username (email) is shown
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "email"

    # Provide email address to config flow
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.request_code",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USER_EMAIL}
        )
        # Check that user form requesting a code is shown
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"

    # Provide code from email to config flow
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.code_login",
        return_value=MOCK_CONFIG.get("user_data"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
        )
    # Check config flow completed and a new entry is created
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]


async def test_invalid_code(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to incorrect code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "email"

    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.request_code",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USER_EMAIL}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
    # Raise exception for invalid code
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.code_login",
        side_effect=RoborockException("invalid code"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
        )
    # Check the user form is presented with the error
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_code"}


async def test_unknown_user(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to credential validation failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "email"

    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.request_code",
        side_effect=RoborockException("unknown user"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "USER_EMAIL"}
        )
    # Check the user form is presented with the error
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_email"}


async def test_reauth(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test reauth flow handles correctly."""
    pass
    # TODO
