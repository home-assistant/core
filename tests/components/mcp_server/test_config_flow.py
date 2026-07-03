"""Test the Model Context Protocol Server config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.mcp_server.const import CONF_LEGACY, DOMAIN
from homeassistant.components.mcp_server.http import STREAMABLE_API, STREAMABLE_API_BASE
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


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
    """Test we get the form."""
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Assist"
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["data"] == {CONF_LLM_HASS_API: ["assist"]}


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


@pytest.mark.parametrize(
    ("legacy", "expected_path"),
    [
        (True, STREAMABLE_API),
        (False, f"{STREAMABLE_API_BASE}/{{entry_id}}"),
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

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    path = expected_path.format(entry_id=config_entry.entry_id)
    placeholders = result["description_placeholders"]
    assert placeholders["internal_url"] == f"http://homeassistant.local:8123{path}"
    assert placeholders["external_url"] == f"https://example.com{path}"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert config_entry.data.get(CONF_LEGACY) == (True if legacy else None)


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


class _MockLLMAPI(llm.API):
    """Test LLM API used to have a second selectable API."""

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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_multiple_config_entries_allowed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that a second config entry exposing different APIs can be created."""
    llm.async_register_api(hass, _MockLLMAPI(hass=hass, id="test-api", name="Test API"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: ["test-api"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_LLM_HASS_API: ["test-api"]}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_config_entry_aborted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that a config entry exposing the same APIs is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
