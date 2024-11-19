"""Test the igloohome config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from igloohome_api import AuthException
from parameterized import parameterized

from homeassistant import config_entries
from homeassistant.components.igloohome.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "igloohome_api.Auth.async_get_access_token",
        return_value="mock_access_token",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Client Credentials"
    assert result["data"] == {
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@parameterized.expand(
    [(AuthException(), "invalid_auth"), (ClientError(), "cannot_connect")]
)
async def test_form_invalid_input(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, auth_exception, result_error
) -> None:
    """Tests where we handle errors in the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "igloohome_api.Auth.async_get_access_token",
        side_effect=auth_exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": result_error}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "igloohome_api.Auth.async_get_access_token",
        return_value="mock_access_token",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Client Credentials"
    assert result["data"] == {
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1
