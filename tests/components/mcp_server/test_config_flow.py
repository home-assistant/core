"""Test the Model Context Protocol Server config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.mcp_server.const import DOMAIN
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    "params",
    [
        {},
        {CONF_LLM_HASS_API: "assist"},
    ],
)
async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, params: dict[str, Any]
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        params,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Assist"
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["data"] == {CONF_LLM_HASS_API: "assist"}
