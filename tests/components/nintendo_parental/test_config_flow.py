"""Test the Nintendo Switch Parental Controls config flow."""

from unittest.mock import AsyncMock

from pynintendoparental.exceptions import InvalidSessionTokenException

from homeassistant import config_entries
from homeassistant.components.nintendo_parental.const import CONF_SESSION_TOKEN, DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ACCOUNT_ID, API_TOKEN, LOGIN_URL

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nintendo_authenticator: AsyncMock,
) -> None:
    """Test a full and successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]
    assert result["description_placeholders"]["link"] == LOGIN_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_ID
    assert result["data"][CONF_SESSION_TOKEN] == API_TOKEN
    assert result["result"].unique_id == ACCOUNT_ID


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_authenticator: AsyncMock,
) -> None:
    """Test that the flow aborts if the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_nintendo_authenticator: AsyncMock,
) -> None:
    """Test handling of invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    # Simulate invalid authentication by raising an exception
    mock_nintendo_authenticator.complete_login.side_effect = (
        InvalidSessionTokenException(status_code=401, message="Test")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "invalid_token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # Now ensure that the flow can be recovered
    mock_nintendo_authenticator.complete_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_ID
    assert result["data"][CONF_SESSION_TOKEN] == API_TOKEN
    assert result["result"].unique_id == ACCOUNT_ID


async def test_reauthentication_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_authenticator: AsyncMock,
) -> None:
    """Test successful reauthentication."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauthentication_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_authenticator: AsyncMock,
) -> None:
    """Test failed reauthentication."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Simulate invalid authentication by raising an exception
    mock_nintendo_authenticator.complete_login.side_effect = (
        InvalidSessionTokenException(status_code=401, message="Test")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    # Now ensure that the flow can be recovered
    mock_nintendo_authenticator.complete_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: API_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
