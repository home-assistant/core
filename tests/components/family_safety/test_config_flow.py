"""Test the Microsoft Family Safety config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyfamilysafety.exceptions import Unauthorized

from homeassistant import config_entries
from homeassistant.components.family_safety.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

mock_config_entry = MockConfigEntry(
    domain=DOMAIN,
    data={CONF_API_TOKEN: "M.C560_BL2.0.U.-tokendata"},
    unique_id="aabbccddee112233",
)


async def test_full_flow(
    hass: HomeAssistant, mock_authenticator_client: MagicMock
) -> None:
    """Test full end to end config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "https://login.live.com/oauth20_desktop.srf?code=M.C560_BL2.0.U.-tokendata"
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_API_TOKEN] == "refresh-token-here"
    assert result["result"].unique_id == "aabbccddee112233"


async def test_already_configured(
    hass: HomeAssistant, mock_authenticator_client: MagicMock
) -> None:
    """Ensure only one instance of an account can be configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "https://login.live.com/oauth20_desktop.srf?code=M.C560_BL2.0.U.-tokendata"
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_api_token(
    hass: HomeAssistant,
    mock_authenticator_client: MagicMock,
) -> None:
    """Test to ensure an error is shown if the API token is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]
    # Patch Authenticator.create directly to raise Unauthorized
    # This ensures the config_flow's try-except block for Unauthorized is hit.
    with (
        patch(
            "homeassistant.components.family_safety.Authenticator.create",
            new_callable=AsyncMock,
            side_effect=Unauthorized,
        ),
        patch(  # Also patch the pyfamilysafety version if it's imported directly
            "pyfamilysafety.Authenticator.create",
            new_callable=AsyncMock,
            side_effect=Unauthorized,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_TOKEN: "https://login.live.com/oauth20_desktop.srf?code=M.C560_BL2.0.U.-tokendata"
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "https://login.live.com/oauth20_desktop.srf?code=M.C560_BL2.0.U.-tokendata"
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_API_TOKEN] == "refresh-token-here"
    assert result["result"].unique_id == "aabbccddee112233"
