"""Test the Gatus config flow."""

from unittest.mock import AsyncMock, patch

from gatus_api.client import GatusClientError

from homeassistant import config_entries
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form, validate the client, and create a successful entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Gatus"
    assert result2["data"] == {
        CONF_URL: "http://gatus.local:8080",
    }

    assert result2["result"].unique_id is not None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_connection_error_and_recovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test handling connection failures and ensuring the flow can completely recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(side_effect=GatusClientError("Cannot connect")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["result"].unique_id is not None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test handling fallback arbitrary exceptions gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.validate_input",
        side_effect=Exception("Unexpected backend explosion"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that duplicate configurations for the same base URL abort early via match mapping."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local:8080"},
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.local:8080"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
