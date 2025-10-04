"""Test the Nintendo Switch Parental Controls config flow."""

from unittest.mock import AsyncMock

from pynintendoparental.exceptions import InvalidSessionTokenException

from homeassistant import config_entries
from homeassistant.components.nintendo_parental.const import CONF_SESSION_TOKEN, DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_SESSION_TOKEN] == "valid_token"
    assert result["result"].unique_id == "aabbccddee112233"


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_authenticator: AsyncMock,
):
    """Test that the flow aborts if the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
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
        InvalidSessionTokenException
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "invalid_token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
