"""Tests for the config LLM tools."""

from collections.abc import Iterable
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    MockUser,
    mock_integration,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components import config as config_component
from homeassistant.components.config.llm import GetConfigEntriesTool, async_get_tools
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

TEST_DOMAIN = "test_llm_config"


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_tools returns tools only for Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    ha_tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert ha_tools is not None
    assert [tool.name for tool in ha_tools.tools] == [
        "config__get_config_entries",
    ]
    assert ha_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that tool schemas can be exported for LLM clients."""
    tools = [GetConfigEntriesTool()]
    assert {
        tool.name: probatio.to_openapi(tool.parameters) for tool in tools
    } == snapshot


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test tool discovery and execution through the Home Assistant API."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    assert await async_setup_component(hass, config_component.DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Philips Hue Bridge",
        entry_id="hue_entry_1",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "config__get_config_entries")
    assert tool.integration == config_component.DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    result = await api.async_call_tool(
        llm.ToolInput(tool.name, {"domain": TEST_DOMAIN})
    )
    assert result == llm.ToolResult(
        data={
            "result": [
                {
                    "entry_id": "hue_entry_1",
                    "domain": TEST_DOMAIN,
                    "title": "Philips Hue Bridge",
                    "state": "loaded",
                }
            ]
        }
    )


async def test_get_config_entries_filtering_and_error_reasons(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test listing and filtering config entries and resolving error reasons."""
    loaded_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Main Entry",
        entry_id="entry_loaded",
        state=ConfigEntryState.LOADED,
    )
    loaded_entry.add_to_hass(hass)

    not_loaded_entry = MockConfigEntry(
        domain="sun",
        title="Sun",
        entry_id="entry_not_loaded",
        state=ConfigEntryState.NOT_LOADED,
    )
    not_loaded_entry.add_to_hass(hass)

    error_entry = MockConfigEntry(
        domain="zwave_js",
        title="Z-Wave Stick",
        entry_id="entry_error",
        state=ConfigEntryState.SETUP_ERROR,
        reason="cannot_connect",
    )
    error_entry.add_to_hass(hass)

    translated_error_entry = MockConfigEntry(
        domain="hue",
        title="Hue Bridge",
        entry_id="entry_translated_error",
    )
    translated_error_entry.add_to_hass(hass)
    translated_error_entry._async_set_state(
        hass,
        ConfigEntryState.SETUP_RETRY,
        None,
        "cannot_connect",
        {"host": "192.168.1.50"},
        "hue",
    )

    disabled_entry = MockConfigEntry(
        domain="spotify",
        title="Spotify",
        entry_id="entry_disabled",
        state=ConfigEntryState.NOT_LOADED,
        disabled_by=ConfigEntryDisabler.USER,
    )
    disabled_entry.add_to_hass(hass)

    ignored_entry = MockConfigEntry(
        domain="hue",
        title="Ignored",
        entry_id="entry_ignored",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)

    tool = GetConfigEntriesTool()

    async def _mock_get_translations(
        hass_obj: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, str]:
        if category == "exceptions":
            return {
                "component.hue.exceptions.cannot_connect.message": (
                    "Failed to connect to bridge at {host}"
                )
            }
        if category == "config":
            return {
                "component.zwave_js.config.error.cannot_connect": (
                    "Failed to connect to Z-Wave stick"
                )
            }
        return {}

    with patch(
        "homeassistant.components.config.llm.translation.async_get_translations",
        side_effect=_mock_get_translations,
    ):
        # Default: returns all entries including disabled and ignored
        all_res = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)
        assert all_res == llm.ToolResult(
            data={
                "result": [
                    {
                        "entry_id": "entry_loaded",
                        "domain": TEST_DOMAIN,
                        "title": "Main Entry",
                        "state": "loaded",
                    },
                    {
                        "entry_id": "entry_not_loaded",
                        "domain": "sun",
                        "title": "Sun",
                        "state": "not_loaded",
                    },
                    {
                        "entry_id": "entry_error",
                        "domain": "zwave_js",
                        "title": "Z-Wave Stick",
                        "state": "setup_error",
                        "reason": "Failed to connect to Z-Wave stick",
                    },
                    {
                        "entry_id": "entry_translated_error",
                        "domain": "hue",
                        "title": "Hue Bridge",
                        "state": "setup_retry",
                        "reason": "Failed to connect to bridge at 192.168.1.50",
                    },
                    {
                        "entry_id": "entry_disabled",
                        "domain": "spotify",
                        "title": "Spotify",
                        "state": "not_loaded",
                        "disabled_by": "user",
                    },
                    {
                        "entry_id": "entry_ignored",
                        "domain": "hue",
                        "title": "Ignored",
                        "state": "not_loaded",
                        "source": "ignore",
                    },
                ]
            }
        )

        # Filter by status="not_loaded" (excludes disabled and ignored entries)
        not_loaded_res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"status": "not_loaded"}),
            llm_context,
        )
        assert not_loaded_res == llm.ToolResult(
            data={
                "result": [
                    {
                        "entry_id": "entry_not_loaded",
                        "domain": "sun",
                        "title": "Sun",
                        "state": "not_loaded",
                    },
                ]
            }
        )

        # Filter by status="disabled" (returns disabled and ignored entries)
        disabled_res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"status": "disabled"}),
            llm_context,
        )
        assert disabled_res == llm.ToolResult(
            data={
                "result": [
                    {
                        "entry_id": "entry_disabled",
                        "domain": "spotify",
                        "title": "Spotify",
                        "state": "not_loaded",
                        "disabled_by": "user",
                    },
                    {
                        "entry_id": "entry_ignored",
                        "domain": "hue",
                        "title": "Ignored",
                        "state": "not_loaded",
                        "source": "ignore",
                    },
                ]
            }
        )

        # Filter by domain list and status="error"
        filtered_res = await tool.async_call(
            hass,
            llm.ToolInput(
                tool.name,
                {"domain": [TEST_DOMAIN, "zwave_js"], "status": "error"},
            ),
            llm_context,
        )
        assert filtered_res == llm.ToolResult(
            data={
                "result": [
                    {
                        "entry_id": "entry_error",
                        "domain": "zwave_js",
                        "title": "Z-Wave Stick",
                        "state": "setup_error",
                        "reason": "Failed to connect to Z-Wave stick",
                    }
                ]
            }
        )
