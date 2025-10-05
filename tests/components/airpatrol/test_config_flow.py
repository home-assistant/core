"""Test the AirPatrol config flow."""

from airpatrol.api import AirPatrolAuthenticationError, AirPatrolError
import pytest

from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_USER_INPUT = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "test_password",
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_airpatrol_client_config_flow
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USER_INPUT[CONF_EMAIL]
    assert result["data"] == {
        **TEST_USER_INPUT,
        CONF_ACCESS_TOKEN: "test_access_token",
    }
    assert result["result"].unique_id == "test_user_id"


async def test_async_step_reauth_confirm_success(
    hass: HomeAssistant, mock_config_entry, mock_airpatrol_client_config_flow
) -> None:
    """Test successful reauthentication via async_step_reauth_confirm."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data[CONF_PASSWORD] == "test_password"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "test_access_token"


async def test_async_step_reauth_confirm_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry,
    mock_airpatrol_client_config_flow,
) -> None:
    """Test reauthentication failure due to invalid credentials."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_airpatrol_client_config_flow.authenticate.side_effect = (
        AirPatrolAuthenticationError("fail")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_airpatrol_client_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "test_password"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "test_access_token"


async def test_async_step_reauth_confirm_another_account_failure(
    hass: HomeAssistant, mock_config_entry, mock_airpatrol_client
) -> None:
    """Test reauthentication failure due to another account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_airpatrol_client.get_unique_id.return_value = "different_user_id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test2@example.com", CONF_PASSWORD: "test_password2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (AirPatrolError("fail"), "cannot_connect"),
        (AirPatrolAuthenticationError("fail"), "invalid_auth"),
        (Exception("fail"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    side_effect,
    expected_error,
    mock_airpatrol_client_config_flow,
) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_airpatrol_client_config_flow.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_airpatrol_client_config_flow.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USER_INPUT[CONF_EMAIL]
    assert result["data"] == {
        **TEST_USER_INPUT,
        CONF_ACCESS_TOKEN: "test_access_token",
    }
    assert result["result"].unique_id == "test_user_id"


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_airpatrol_client_config_flow,
    mock_config_entry,
) -> None:
    """Test user flow when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
