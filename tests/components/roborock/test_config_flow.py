"""Test Roborock config flow."""
from unittest.mock import patch

from roborock.exceptions import RoborockException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.roborock.const import CONF_ENTRY_CODE, DOMAIN
from homeassistant.core import HomeAssistant

from .mock_data import MOCK_CONFIG, USER_EMAIL


async def config_flow_helper(
    hass: HomeAssistant,
    request_code_side_effect: Exception | None = None,
    request_code_errors: dict[str, str] | None = None,
    code_login_side_effect: Exception | None = None,
    code_login_errors: dict[str, str] | None = None,
) -> None:
    """Handle applying errors to request code or code login and recovering from the errors."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    if request_code_side_effect:
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockClient.request_code",
            side_effect=request_code_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"username": USER_EMAIL}
            )
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["errors"] == request_code_errors
    # Recover from error if it exist
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.request_code"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USER_EMAIL}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
        assert result["errors"] == {}
    # Raise exception for invalid code
    if code_login_side_effect:
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockClient.code_login",
            side_effect=code_login_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == code_login_errors
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockClient.code_login",
        return_value=MOCK_CONFIG["user_data"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]


async def test_invalid_code(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to incorrect code."""
    await config_flow_helper(
        hass,
        code_login_side_effect=RoborockException(),
        code_login_errors={"base": "invalid_code"},
    )


async def test_code_unknown_error(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to an unknown error in request code."""
    await config_flow_helper(
        hass,
        code_login_side_effect=Exception(),
        code_login_errors={"base": "unknown"},
    )


async def test_user_does_not_exist(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to credential validation failure."""
    await config_flow_helper(
        hass,
        request_code_side_effect=RoborockException(),
        request_code_errors={"base": "invalid_email"},
    )


async def test_user_unknown_error(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test a failed config flow due to an unknown error during code login."""
    await config_flow_helper(
        hass,
        request_code_side_effect=Exception(),
        request_code_errors={"base": "unknown"},
    )
