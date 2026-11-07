"""Tests for the Model Context Protocol diagnostics."""

from unittest.mock import AsyncMock

from mcp.types import (
    Implementation,
    InitializeResult,
    ListToolsResult,
    ServerCapabilities,
    Tool,
    ToolAnnotations,
    ToolsCapability,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mcp.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from .conftest import API_TOKEN, TEST_API_NAME


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param({CONF_URL: "http://1.1.1.1/sse"}, id="no_auth"),
        pytest.param(
            {CONF_URL: "http://1.1.1.1/sse", CONF_API_TOKEN: API_TOKEN},
            id="api_token",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mcp_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entry_data: dict[str, str],
) -> None:
    """Test config entry diagnostics."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title=TEST_API_NAME)
    config_entry.add_to_hass(hass)
    session = mock_mcp_client.return_value
    session.initialize.return_value = InitializeResult(
        protocolVersion="2025-03-26",
        capabilities=ServerCapabilities(tools=ToolsCapability(listChanged=True)),
        serverInfo=Implementation(name=TEST_API_NAME, version="1.0.0"),
    )
    session.list_tools.return_value = ListToolsResult(
        tools=[
            Tool(
                name="search_memory",
                title="Search memory",
                description="Search memory for relevant context based on a query.",
                inputSchema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A free text query to search context for.",
                        }
                    },
                },
                annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            )
        ]
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
