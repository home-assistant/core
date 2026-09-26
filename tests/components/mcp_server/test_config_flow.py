"""Test the Model Context Protocol Server config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.mcp_server.const import CONF_REQUIRE_ADMIN, DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from .conftest import TEST_LLM_API_ID, MockLLMAPI

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
    assert result["minor_version"] == 2
    assert result["data"] == {
        CONF_LLM_HASS_API: ["assist"],
        CONF_REQUIRE_ADMIN: True,
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


async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test changing the LLM APIs in the options flow."""
    llm.async_register_api(hass, MockLLMAPI(hass=hass, id=TEST_LLM_API_ID, name="Test"))
    # The title generated for the APIs the entry was created with
    hass.config_entries.async_update_entry(config_entry, title="Assist")
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]
    assert result["data_schema"]({}) == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LLM_HASS_API: [llm.LLM_API_ASSIST, TEST_LLM_API_ID],
            CONF_REQUIRE_ADMIN: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST, TEST_LLM_API_ID],
        CONF_REQUIRE_ADMIN: True,
    }
    assert config_entry.title == "Assist, Test"


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST])
async def test_options_flow_legacy_single_api(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the form defaults for an entry that stored a single API as a string."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({}) == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST], CONF_REQUIRE_ADMIN: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }


async def test_options_flow_keeps_custom_title(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the options flow does not overwrite a title the user changed."""
    llm.async_register_api(hass, MockLLMAPI(hass=hass, id=TEST_LLM_API_ID, name="Test"))
    hass.config_entries.async_update_entry(config_entry, title="My MCP server")
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [TEST_LLM_API_ID], CONF_REQUIRE_ADMIN: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        CONF_LLM_HASS_API: [TEST_LLM_API_ID],
        CONF_REQUIRE_ADMIN: False,
    }
    assert config_entry.title == "My MCP server"


async def test_options_flow_errors(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the options flow requires at least one LLM API."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [], CONF_REQUIRE_ADMIN: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LLM_HASS_API: "llm_api_required"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST], CONF_REQUIRE_ADMIN: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }


async def test_options_flow_unmigrated_entry(hass: HomeAssistant) -> None:
    """Test the options flow on a disabled config entry that has not migrated."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
        minor_version=1,
        disabled_by=ConfigEntryDisabler.USER,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({}) == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST], CONF_REQUIRE_ADMIN: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data[CONF_REQUIRE_ADMIN] is True
