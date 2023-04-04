"""Test Roborock config flow."""
from unittest.mock import patch

import pytest
from roborock.exceptions import RoborockException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.roborock.const import CONF_ENTRY_CODE, DOMAIN
from homeassistant.core import HomeAssistant

from .mock_data import MOCK_CONFIG, USER_EMAIL


@pytest.mark.parametrize(
    (
        "request_code_side_effect",
        "request_code_errors",
        "code_login_side_effect",
        "code_login_errors",
    ),
    [
        (None, {}, RoborockException(), {"base": "invalid_code"}),
        (None, {}, Exception(), {"base": "unknown"}),
        (RoborockException(), {"base": "invalid_email"}, None, {}),
        (Exception(), {"base": "unknown"}, None, {}),
    ],
)
async def test_config_flow_failures(
    hass: HomeAssistant,
    bypass_api_fixture,
    request_code_side_effect: Exception | None,
    request_code_errors: dict[str, str],
    code_login_side_effect: Exception | None,
    code_login_errors: dict[str, str],
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
