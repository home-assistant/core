"""Test the Gatus config flow."""

from unittest.mock import AsyncMock, patch

from gatus_api.client import GatusClientError
import pytest

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gatus"
    assert result["data"] == {
        CONF_URL: "http://gatus.local:8080",
    }

    assert result["result"].unique_id == "gatus.local:8080"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (GatusClientError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_form_failures_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test handling validation failures and ensuring the flow can completely recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "gatus.local:8080"
    assert len(mock_setup_entry.mock_calls) == 1


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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.local:8080"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_already_configured_by_unique_id(hass: HomeAssistant) -> None:
    """Test that configurations with different URLs but matching unique IDs abort correctly."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local:8080/"},
        unique_id="gatus.local:8080",
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
