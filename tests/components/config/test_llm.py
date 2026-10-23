"""Tests for the config LLM tools."""

from typing import Any
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


MOCK_EXCEPTION_TRANSLATIONS: dict[str, str] = {
    "component.hue.exceptions.cannot_connect.message": (
        "Failed to connect to bridge at {host}."
    ),
}


@pytest.mark.parametrize(
    ("tool_args", "expected_result"),
    [
        pytest.param(
            {},
            [
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
                    "entry_id": "entry_setup_in_progress",
                    "domain": "matter",
                    "title": "Matter",
                    "state": "setup_in_progress",
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
                    "entry_id": "entry_untranslated_exc_error",
                    "domain": "hue",
                    "title": "Hue Bridge 2",
                    "state": "setup_error",
                    "reason": "auth_failed_key",
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
            ],
            id="all_entries",
        ),
        pytest.param(
            {"status": "loaded"},
            [
                {
                    "entry_id": "entry_loaded",
                    "domain": TEST_DOMAIN,
                    "title": "Main Entry",
                    "state": "loaded",
                },
            ],
            id="status_loaded",
        ),
        pytest.param(
            {"status": "not_loaded"},
            [
                {
                    "entry_id": "entry_not_loaded",
                    "domain": "sun",
                    "title": "Sun",
                    "state": "not_loaded",
                },
                {
                    "entry_id": "entry_setup_in_progress",
                    "domain": "matter",
                    "title": "Matter",
                    "state": "setup_in_progress",
                },
            ],
            id="status_not_loaded",
        ),
        pytest.param(
            {"status": "disabled"},
            [
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
            ],
            id="status_disabled",
        ),
        pytest.param(
            {"domain": [TEST_DOMAIN, "  ZWAVE_JS  "], "status": "error"},
            [
                {
                    "entry_id": "entry_error",
                    "domain": "zwave_js",
                    "title": "Z-Wave Stick",
                    "state": "setup_error",
                    "reason": "Failed to connect to Z-Wave stick",
                },
            ],
            id="domain_list_and_status_error",
        ),
        pytest.param(
            {"domain": "  HUE  ", "status": "error"},
            [
                {
                    "entry_id": "entry_translated_error",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "state": "setup_retry",
                    "reason": "Failed to connect to bridge at 192.168.1.50",
                },
                {
                    "entry_id": "entry_untranslated_exc_error",
                    "domain": "hue",
                    "title": "Hue Bridge 2",
                    "state": "setup_error",
                    "reason": "auth_failed_key",
                },
            ],
            id="single_domain_and_missing_translation_fallback",
        ),
    ],
)
async def test_get_config_entries_filtering_and_error_reasons(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: dict[str, Any],
    expected_result: list[dict[str, Any]],
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

    setup_in_progress_entry = MockConfigEntry(
        domain="matter",
        title="Matter",
        entry_id="entry_setup_in_progress",
        state=ConfigEntryState.SETUP_IN_PROGRESS,
    )
    setup_in_progress_entry.add_to_hass(hass)

    error_entry = MockConfigEntry(
        domain="zwave_js",
        title="Z-Wave Stick",
        entry_id="entry_error",
        state=ConfigEntryState.SETUP_ERROR,
        reason="Failed to connect to Z-Wave stick",
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

    untranslated_exc_entry = MockConfigEntry(
        domain="hue",
        title="Hue Bridge 2",
        entry_id="entry_untranslated_exc_error",
    )
    untranslated_exc_entry.add_to_hass(hass)
    untranslated_exc_entry._async_set_state(
        hass,
        ConfigEntryState.SETUP_ERROR,
        None,
        "auth_failed_key",
        None,
        None,
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

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value=MOCK_EXCEPTION_TRANSLATIONS,
    ):
        res = await tool.async_call(
            hass, llm.ToolInput(tool.name, tool_args), llm_context
        )
        assert res == llm.ToolResult(data={"result": expected_result})


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"domain": ""}, id="empty_domain_str"),
        pytest.param({"domain": "   "}, id="whitespace_domain_str"),
        pytest.param({"domain": []}, id="empty_domain_list"),
        pytest.param({"domain": ["   "]}, id="whitespace_domain_list"),
        pytest.param({"status": "invalid"}, id="invalid_status"),
    ],
)
async def test_get_config_entries_invalid_args(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    invalid_args: dict[str, Any],
) -> None:
    """Test that invalid domain or status arguments raise probatio.Invalid."""
    tool = GetConfigEntriesTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, invalid_args), llm_context)
