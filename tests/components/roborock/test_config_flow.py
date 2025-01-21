"""Test Roborock config flow."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from roborock import RoborockTooFrequentCodeRequests
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockUrlException,
)
from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant import config_entries
from homeassistant.components.roborock.const import CONF_ENTRY_CODE, DOMAIN, DRAWABLES
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .mock_data import MOCK_CONFIG, USER_DATA, USER_EMAIL

from tests.common import MockConfigEntry


async def test_config_flow_success(
    hass: HomeAssistant,
    bypass_api_fixture,
) -> None:
    """Handle the config flow and make sure it succeeds."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "request_code_side_effect",
        "request_code_errors",
    ),
    [
        (RoborockException(), {"base": "unknown_roborock"}),
        (RoborockAccountDoesNotExist(), {"base": "invalid_email"}),
        (RoborockInvalidEmail(), {"base": "invalid_email_format"}),
        (RoborockTooFrequentCodeRequests(), {"base": "too_frequent_code_requests"}),
        (RoborockUrlException(), {"base": "unknown_url"}),
        (Exception(), {"base": "unknown"}),
    ],
)
async def test_config_flow_failures_request_code(
    hass: HomeAssistant,
    bypass_api_fixture,
    request_code_side_effect: Exception | None,
    request_code_errors: dict[str, str],
) -> None:
    """Handle applying errors to request code recovering from the errors."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code",
            side_effect=request_code_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )
            assert result["type"] is FlowResultType.FORM
            assert result["errors"] == request_code_errors
        # Recover from error
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "code_login_side_effect",
        "code_login_errors",
    ),
    [
        (RoborockException(), {"base": "unknown_roborock"}),
        (RoborockInvalidCode(), {"base": "invalid_code"}),
        (Exception(), {"base": "unknown"}),
    ],
)
async def test_config_flow_failures_code_login(
    hass: HomeAssistant,
    bypass_api_fixture,
    code_login_side_effect: Exception | None,
    code_login_errors: dict[str, str],
) -> None:
    """Handle applying errors to code login and recovering from the errors."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        # Raise exception for invalid code
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            side_effect=code_login_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == code_login_errors
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


async def test_options_flow_drawables(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == DRAWABLES
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={Drawable.PREDICTED_PATH: True},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[DRAWABLES][Drawable.PREDICTED_PATH] is True
    assert len(mock_setup.mock_calls) == 1


async def test_reauth_flow(
    hass: HomeAssistant, bypass_api_fixture, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow."""
    # Start reauth
    result = mock_roborock_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    # Request a new code
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    # Enter a new code
    assert result["step_id"] == "code"
    assert result["type"] is FlowResultType.FORM
    new_user_data = deepcopy(USER_DATA)
    new_user_data.rriot.s = "new_password_hash"
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
        return_value=new_user_data,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_roborock_entry.data["user_data"]["rriot"]["s"] == "new_password_hash"


async def test_account_already_configured(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Handle the config flow and make sure it succeeds."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "already_configured_account"
