"""Test the Nintendo Switch Parental Controls config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.nintendo_parental.const import CONF_SESSION_TOKEN, DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


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
