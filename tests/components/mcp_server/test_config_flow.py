"""Test the Model Context Protocol Server config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mcp_server.const import CONF_URL_ID, DOMAIN
from homeassistant.components.mcp_server.http import STREAMABLE_API_BASE
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


class _MockLLMAPI(llm.API):
    """Test LLM API used to provide additional selectable APIs."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return a test API instance."""
        return llm.APIInstance(
            api=self,
            api_prompt="Test prompt",
            llm_context=llm_context,
            tools=[],
        )


@pytest.mark.parametrize(
    "params",
    [
        {},
        {CONF_LLM_HASS_API: ["assist"]},
    ],
)
async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, params: dict[str, Any]
) -> None:
    """Test the full create flow shows the URLs before creating the entry."""
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://homeassistant.local:8123",
            "external_url": "https://example.com",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        params,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "finish"
    path = f"{STREAMABLE_API_BASE}/assist"
    placeholders = result["description_placeholders"]
    assert placeholders["name"] == "Assist"
    assert placeholders["internal_url"] == f"http://homeassistant.local:8123{path}"
    assert placeholders["external_url"] == f"https://example.com{path}"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Assist"
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["data"] == {
        CONF_LLM_HASS_API: ["assist"],
        CONF_URL_ID: "assist",
    }


@pytest.mark.parametrize(
    ("params", "errors"),
    [
        ({CONF_LLM_HASS_API: []}, {CONF_LLM_HASS_API: "llm_api_required"}),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant, params: dict[str, Any], errors: dict[str, str]
) -> None:
    """Test we get the errors on invalid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        params,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_multiple_apis_generic_name(hass: HomeAssistant) -> None:
    """Test a generic name and random URL identifier are used for many APIs."""
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-2", name="API 2"))
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-3", name="API 3"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.mcp_server.config_flow.secrets.token_hex",
        return_value="abc123",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LLM_HASS_API: ["assist", "api-2", "api-3"]},
        )
        assert result["step_id"] == "finish"
        assert result["description_placeholders"]["name"] == "MCP Server"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MCP Server"
    assert result["data"][CONF_URL_ID] == "abc123"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_generic_name_counter(hass: HomeAssistant) -> None:
    """Test the generic name gets a counter when it is already taken."""
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-2", name="API 2"))
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-3", name="API 3"))
    MockConfigEntry(
        domain=DOMAIN,
        title="MCP Server",
        data={CONF_LLM_HASS_API: ["assist", "api-2", "api-3"], CONF_URL_ID: "aaaaaa"},
        minor_version=2,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.mcp_server.config_flow.secrets.token_hex",
        return_value="bbbbbb",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LLM_HASS_API: ["assist", "api-2", "api-3"]},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MCP Server 2"


@pytest.mark.parametrize("legacy", [False])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_url_id_collision(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a second entry with the same APIs gets a unique URL identifier."""
    assert config_entry.data[CONF_URL_ID] == "assist"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: ["assist"]},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LLM_HASS_API] == ["assist"]
    assert result["data"][CONF_URL_ID] == "assist_2"
