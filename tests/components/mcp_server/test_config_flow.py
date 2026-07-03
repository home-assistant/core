"""Test the Model Context Protocol Server config flow."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mcp_server.const import CONF_LEGACY, CONF_URL_ID, DOMAIN
from homeassistant.components.mcp_server.http import STREAMABLE_API, STREAMABLE_API_BASE
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
async def test_form_multiple_apis_derives_url_id(hass: HomeAssistant) -> None:
    """Test the URL identifier is derived from the API IDs when AI Task is absent."""
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-2", name="API 2"))
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-3", name="API 3"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: ["assist", "api-2", "api-3"]},
    )
    assert result["step_id"] == "finish"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Assist, API 2, API 3"
    assert result["data"][CONF_URL_ID] == "assist_api_2_api_3"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_multiple_apis_uses_ai_task(hass: HomeAssistant) -> None:
    """Test an AI Task proposes the name and URL identifier for multiple APIs."""
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-2", name="API 2"))
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-3", name="API 3"))
    hass.config.components.add("ai_task")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.mcp_server.config_flow.ai_task.async_generate_data",
        return_value=Mock(data={"title": "Home Bot", "slug": "home_bot"}),
    ) as mock_generate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LLM_HASS_API: ["assist", "api-2", "api-3"]},
        )
    assert mock_generate.called
    assert result["step_id"] == "finish"
    assert result["description_placeholders"]["name"] == "Home Bot"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Bot"
    assert result["data"][CONF_URL_ID] == "home_bot"


@pytest.mark.parametrize("legacy", [False])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_url_id_collision(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a colliding URL identifier is made unique with a suffix."""
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
    assert result["data"][CONF_URL_ID] == "assist_2"


@pytest.mark.parametrize(
    ("legacy", "expected_path"),
    [
        (True, STREAMABLE_API),
        (False, f"{STREAMABLE_API_BASE}/assist"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    legacy: bool,
    expected_path: str,
) -> None:
    """Test reconfiguring an entry shows the URLs and updates the APIs."""
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://homeassistant.local:8123",
            "external_url": "https://example.com",
        },
    )
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="api-2", name="API 2"))

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    placeholders = result["description_placeholders"]
    assert (
        placeholders["internal_url"]
        == f"http://homeassistant.local:8123{expected_path}"
    )
    assert placeholders["external_url"] == f"https://example.com{expected_path}"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST, "api-2"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST, "api-2"]
    # The URL identifier and legacy flag remain stable across reconfigure
    assert config_entry.data.get(CONF_LEGACY) == (True if legacy else None)
    assert config_entry.data.get(CONF_URL_ID) == (None if legacy else "assist")


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_requires_llm_api(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure validates that an LLM API is selected."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: []},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LLM_HASS_API: "llm_api_required"}


@pytest.mark.parametrize("legacy", [False])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_apis_allowed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a second entry exposing the same APIs is allowed on a new URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert result["data"][CONF_URL_ID] == "assist_2"
