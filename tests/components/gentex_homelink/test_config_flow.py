"""Test the homelink config flow."""

from unittest.mock import patch

import botocore.exceptions

from homeassistant import config_entries
from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM


async def test_full_flow(hass: HomeAssistant) -> None:
    """Check full flow."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access",
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]
        assert result["data"]["token"]
        assert result["data"]["token"]["access_token"] == "access"
        assert result["data"]["token"]["refresh_token"] == "refresh"
        assert result["data"]["token"]["expires_in"] == 3600
        assert result["data"]["token"]["expires_at"]


async def test_boto_error(hass: HomeAssistant) -> None:
    """Test exceptions from boto are handled correctly."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.side_effect = botocore.exceptions.ClientError(
            {"Error": {}}, "Some operation"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_generic_error(hass: HomeAssistant) -> None:
    """Test exceptions from boto are handled correctly."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.side_effect = Exception("Some error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
