"""Test the FENIX Control config flow."""

from unittest.mock import MagicMock

from pyfenixcontrol import (
    FenixControlAuthError,
    FenixControlConnectionError,
    FenixControlResponseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fenix_control.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import EMAIL, PASSWORD, USER_ID

ERRORS = [
    pytest.param(FenixControlAuthError("rejected"), "invalid_auth", id="invalid_auth"),
    pytest.param(
        FenixControlConnectionError("offline"), "cannot_connect", id="cannot_connect"
    ),
    pytest.param(
        FenixControlResponseError("HTTP 500", 500), "cannot_connect", id="response"
    ),
    pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_fenix_client: MagicMock) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    assert result["result"].unique_id == USER_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors in the user flow and recovery afterwards."""
    mock_fenix_client.get_user_id.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_fenix_client.get_user_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}


@pytest.mark.usefixtures("mock_fenix_client", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an account can only be added once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "other@example.com", CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _suggested_email(result: ConfigFlowResult) -> str:
    """Return the e-mail address pre-filled in a form."""
    key = next(key for key in result["data_schema"].schema if key == CONF_EMAIL)
    return key.description["suggested_value"]


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "email",
    [
        pytest.param(EMAIL, id="same_email"),
        pytest.param("new@example.com", id="changed_email"),
    ],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
    email: str,
) -> None:
    """Test reauthentication with a new password and possibly a new e-mail."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert _suggested_email(result) == EMAIL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: email, CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_EMAIL: email, CONF_PASSWORD: "new-password"}
    assert mock_config_entry.unique_id == USER_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), ERRORS)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors in the reauth flow and recovery afterwards."""
    mock_config_entry.add_to_hass(hass)
    mock_fenix_client.get_user_id.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "typo@example.com", CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # The form keeps the e-mail address that was entered
    assert _suggested_email(result) == "typo@example.com"

    mock_fenix_client.get_user_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test that reauthentication can't switch to another account."""
    mock_config_entry.add_to_hass(hass)
    mock_fenix_client.get_user_id.return_value = "another-account"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "other@example.com", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data == {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
