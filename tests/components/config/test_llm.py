"""Tests for the config LLM tools."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, override
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    MockUser,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import config as config_component
from homeassistant.components.config.llm import (
    ConfigureFlowTool,
    GetConfigEntriesTool,
    ReloadConfigEntryTool,
    SearchIntegrationsTool,
    StartFlowTool,
    async_get_tools,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, DependencyError
from homeassistant.helpers import config_entry_oauth2_flow, llm, selector
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
        "config__reload_config_entry",
        "config__search_integrations",
        "config__start_flow",
        "config__configure_flow",
    ]
    assert ha_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that tool schemas can be exported for LLM clients."""
    tools = [
        GetConfigEntriesTool(),
        ReloadConfigEntryTool(),
        SearchIntegrationsTool(),
        StartFlowTool(),
        ConfigureFlowTool(),
    ]
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
        entry_id="01J00000000000000000001001",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "config__get_config_entries")
    assert tool.integration == config_component.DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    reload_tool = next(
        tool for tool in api.tools if tool.name == "config__reload_config_entry"
    )
    assert reload_tool.integration == config_component.DOMAIN
    assert reload_tool.annotations == llm.ToolAnnotations(
        read_only=False, destructive=False, idempotent=True, open_world=False
    )

    search_tool = next(
        tool for tool in api.tools if tool.name == "config__search_integrations"
    )
    assert search_tool.integration == config_component.DOMAIN
    assert search_tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    start_tool = next(tool for tool in api.tools if tool.name == "config__start_flow")
    assert start_tool.integration == config_component.DOMAIN
    assert start_tool.annotations == llm.ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )

    configure_tool = next(
        tool for tool in api.tools if tool.name == "config__configure_flow"
    )
    assert configure_tool.integration == config_component.DOMAIN
    assert configure_tool.annotations == llm.ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )

    result = await api.async_call_tool(
        llm.ToolInput(tool.name, {"domain": TEST_DOMAIN})
    )
    assert result == llm.ToolResult(
        data={
            "result": [
                {
                    "entry_id": f"{TEST_DOMAIN}:1001",
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
                    "entry_id": f"{TEST_DOMAIN}:1001",
                    "domain": TEST_DOMAIN,
                    "title": "Main Entry",
                    "state": "loaded",
                },
                {
                    "entry_id": "sun:1002",
                    "domain": "sun",
                    "title": "Sun",
                    "state": "not_loaded",
                },
                {
                    "entry_id": "matter:1003",
                    "domain": "matter",
                    "title": "Matter",
                    "state": "setup_in_progress",
                },
                {
                    "entry_id": "zwave_js:1004",
                    "domain": "zwave_js",
                    "title": "Z-Wave Stick",
                    "state": "setup_error",
                    "reason": "Failed to connect to Z-Wave stick",
                },
                {
                    "entry_id": "hue:A8K2M",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "state": "setup_retry",
                    "reason": "Failed to connect to bridge at 192.168.1.50",
                },
                {
                    "entry_id": "hue:B8K2M",
                    "domain": "hue",
                    "title": "Hue Bridge 2",
                    "state": "setup_error",
                    "reason": "auth_failed_key",
                },
                {
                    "entry_id": "spotify:1005",
                    "domain": "spotify",
                    "title": "Spotify",
                    "state": "not_loaded",
                    "disabled_by": "user",
                },
                {
                    "entry_id": "hue:1006",
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
                    "entry_id": f"{TEST_DOMAIN}:1001",
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
                    "entry_id": "sun:1002",
                    "domain": "sun",
                    "title": "Sun",
                    "state": "not_loaded",
                },
                {
                    "entry_id": "matter:1003",
                    "domain": "matter",
                    "title": "Matter",
                    "state": "setup_in_progress",
                },
                {
                    "entry_id": "spotify:1005",
                    "domain": "spotify",
                    "title": "Spotify",
                    "state": "not_loaded",
                    "disabled_by": "user",
                },
                {
                    "entry_id": "hue:1006",
                    "domain": "hue",
                    "title": "Ignored",
                    "state": "not_loaded",
                    "source": "ignore",
                },
            ],
            id="status_not_loaded",
        ),
        pytest.param(
            {"domain": [TEST_DOMAIN, "  ZWAVE_JS  "], "status": "error"},
            [
                {
                    "entry_id": "zwave_js:1004",
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
                    "entry_id": "hue:A8K2M",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "state": "setup_retry",
                    "reason": "Failed to connect to bridge at 192.168.1.50",
                },
                {
                    "entry_id": "hue:B8K2M",
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
        entry_id="01J00000000000000000001001",
        state=ConfigEntryState.LOADED,
    )
    loaded_entry.add_to_hass(hass)

    not_loaded_entry = MockConfigEntry(
        domain="sun",
        title="Sun",
        entry_id="01J00000000000000000001002",
        state=ConfigEntryState.NOT_LOADED,
    )
    not_loaded_entry.add_to_hass(hass)

    setup_in_progress_entry = MockConfigEntry(
        domain="matter",
        title="Matter",
        entry_id="01J00000000000000000001003",
        state=ConfigEntryState.SETUP_IN_PROGRESS,
    )
    setup_in_progress_entry.add_to_hass(hass)

    error_entry = MockConfigEntry(
        domain="zwave_js",
        title="Z-Wave Stick",
        entry_id="01J00000000000000000001004",
        state=ConfigEntryState.SETUP_ERROR,
        reason="Failed to connect to Z-Wave stick",
    )
    error_entry.add_to_hass(hass)

    translated_error_entry = MockConfigEntry(
        domain="hue",
        title="Hue Bridge",
        entry_id="01J000000000000000000A8K2M",
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
        entry_id="01J000000000000000000B8K2M",
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
        entry_id="01J00000000000000000001005",
        state=ConfigEntryState.NOT_LOADED,
        disabled_by=ConfigEntryDisabler.USER,
    )
    disabled_entry.add_to_hass(hass)

    ignored_entry = MockConfigEntry(
        domain="hue",
        title="Ignored",
        entry_id="01J00000000000000000001006",
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


async def test_reload_config_entry_success(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test reloading a config entry by short ID."""
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=AsyncMock(return_value=None),
            async_unload_entry=AsyncMock(return_value=None),
        ),
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)
    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Reloadable Entry",
        entry_id="01J00000000000000000001001",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    hass.config.components.add(TEST_DOMAIN)

    tool = ReloadConfigEntryTool()
    with mock_config_flow(TEST_DOMAIN, config_entries.ConfigFlow):
        res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"entry_id": f"{TEST_DOMAIN}:1001"}),
            llm_context,
        )
    assert res == llm.ToolResult(
        data={
            "result": {
                "entry_id": f"{TEST_DOMAIN}:1001",
                "state": "loaded",
            }
        }
    )


async def test_reload_config_entry_setup_failure_reason(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test reloading a config entry that fails setup with a reason."""
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=AsyncMock(
                side_effect=ConfigEntryError("Failed to connect to Z-Wave stick")
            ),
            async_unload_entry=AsyncMock(return_value=None),
        ),
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)
    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Z-Wave Stick",
        entry_id="01J00000000000000000001004",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    hass.config.components.add(TEST_DOMAIN)

    tool = ReloadConfigEntryTool()
    with mock_config_flow(TEST_DOMAIN, config_entries.ConfigFlow):
        res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"entry_id": f"{TEST_DOMAIN}:1004"}),
            llm_context,
        )
    assert res == llm.ToolResult(
        data={
            "result": {
                "entry_id": f"{TEST_DOMAIN}:1004",
                "state": "setup_error",
                "reason": "Failed to connect to Z-Wave stick",
            }
        }
    )


@pytest.mark.parametrize(
    "entry_id",
    [
        pytest.param("01J00000000000000000001099", id="missing_colon"),
        pytest.param("hue:9999", id="short_id"),
        pytest.param("hue:99", id="suffix_too_short"),
    ],
)
async def test_reload_config_entry_not_found(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    entry_id: str,
) -> None:
    """Test reloading a non-existent config entry."""
    entry = MockConfigEntry(
        domain="hue",
        title="Hue",
        entry_id="01J00000000000000000001099",
    )
    entry.add_to_hass(hass)

    tool = ReloadConfigEntryTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entry_id": entry_id}),
        llm_context,
    )
    assert res == llm.ToolResult(
        data={"error": f"Config entry '{entry_id}' not found."},
        error=True,
    )


async def test_reload_config_entry_ambiguous_short_id(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
) -> None:
    """Test reloading with a short suffix that matches multiple entries in a domain."""
    hue_1 = MockConfigEntry(
        domain="hue",
        title="Hue 1",
        entry_id="01J000000000000000000A8K2M",
    )
    hue_1.add_to_hass(hass)

    hue_2 = MockConfigEntry(
        domain="hue",
        title="Hue 2",
        entry_id="01J000000000000000000B8K2M",
    )
    hue_2.add_to_hass(hass)

    tool = ReloadConfigEntryTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entry_id": "hue:8K2M"}),
        llm_context,
    )
    assert res == llm.ToolResult(
        data={"error": "Config entry 'hue:8K2M' not found."},
        error=True,
    )


@pytest.mark.parametrize(
    ("entry_kwargs", "expected_error"),
    [
        pytest.param(
            {"disabled_by": ConfigEntryDisabler.USER},
            "Config entry 'hue:1005' cannot be reloaded because it is disabled.",
            id="disabled",
        ),
        pytest.param(
            {"source": config_entries.SOURCE_IGNORE},
            "Config entry 'hue:1005' cannot be reloaded because it is ignored.",
            id="ignored",
        ),
    ],
)
async def test_reload_config_entry_disabled_or_ignored(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    entry_kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    """Test that disabled or ignored config entries cannot be reloaded."""
    entry = MockConfigEntry(
        domain="hue",
        title="Hue",
        entry_id="01J00000000000000000001005",
        **entry_kwargs,
    )
    entry.add_to_hass(hass)

    tool = ReloadConfigEntryTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entry_id": "hue:1005"}),
        llm_context,
    )
    assert res == llm.ToolResult(
        data={"error": expected_error},
        error=True,
    )


async def test_reload_config_entry_operation_not_allowed(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
) -> None:
    """Test reloading a config entry in a non-recoverable state."""
    mock_integration(hass, MockModule("hue"))
    unrecoverable_entry = MockConfigEntry(
        domain="hue",
        title="Broken",
        entry_id="01J00000000000000000001007",
        state=ConfigEntryState.MIGRATION_ERROR,
    )
    unrecoverable_entry.add_to_hass(hass)
    hass.config.components.add("hue")

    tool = ReloadConfigEntryTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entry_id": "hue:1007"}),
        llm_context,
    )
    assert res == llm.ToolResult(
        data={
            "error": (
                "Config entry 'hue:1007' cannot be reloaded in state 'migration_error'."
            )
        },
        error=True,
    )


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({}, id="missing_entry_id"),
        pytest.param({"entry_id": ""}, id="empty_entry_id"),
        pytest.param({"entry_id": "   "}, id="whitespace_entry_id"),
    ],
)
async def test_reload_config_entry_invalid_args(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    invalid_args: dict[str, Any],
) -> None:
    """Test that invalid entry_id arguments raise probatio.Invalid."""
    tool = ReloadConfigEntryTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, invalid_args), llm_context)


@pytest.mark.parametrize(
    ("tool_args", "expected_prefix", "expected_domains"),
    [
        pytest.param(
            {"query": "random", "type": "helper"},
            [{"domain": "random", "name": "Random"}],
            {"random"},
            id="helper_exact",
        ),
        pytest.param(
            {"query": "sun", "type": "integration"},
            [{"domain": "sun", "name": "Sun"}],
            {"sun"},
            id="integration_exact",
        ),
        pytest.param(
            {"query": "Times of the Day"},
            [{"domain": "tod", "name": "Times of the Day Sensor"}],
            {"tod"},
            id="translated_title_match",
        ),
        pytest.param(
            {"query": "yale"},
            [],
            {"august", "yalexs_ble"},
            id="brand_exact_match",
        ),
        pytest.param(
            {"query": "yal"},
            [],
            {"august", "yalexs_ble"},
            id="brand_substring_match",
        ),
        pytest.param(
            {"query": "actiontec"},
            [],
            set(),
            id="yaml_only_excluded",
        ),
        pytest.param(
            {"query": "bega"},
            [],
            set(),
            id="iot_standard_only_excluded",
        ),
        pytest.param(
            {"query": "homeassistant_yellow"},
            [],
            set(),
            id="hardware_excluded",
        ),
    ],
)
async def test_search_integrations(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: dict[str, Any],
    expected_prefix: list[dict[str, Any]],
    expected_domains: set[str],
) -> None:
    """Test searching available config-flow integrations and helpers."""
    tool = SearchIntegrationsTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, tool_args),
        llm_context,
    )
    assert res.error is False
    assert isinstance(items := res.data["result"], list)
    assert items[: len(expected_prefix)] == expected_prefix
    domains = {item["domain"] for item in items if isinstance(item, dict)}
    assert expected_domains <= domains
    assert bool(domains) is bool(expected_domains)


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({}, id="missing_query"),
        pytest.param({"query": ""}, id="empty_query"),
        pytest.param({"query": "   "}, id="whitespace_query"),
        pytest.param({"query": "hue", "type": "unknown"}, id="invalid_type"),
    ],
)
async def test_search_integrations_invalid_args(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    invalid_args: dict[str, Any],
) -> None:
    """Test invalid arguments are rejected by SearchIntegrationsTool."""
    tool = SearchIntegrationsTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, invalid_args), llm_context)


async def test_start_and_configure_multi_step_config_flow(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test driving a real built-in multi-step MENU -> FORM -> CREATE_ENTRY config flow (random)."""
    start_tool = StartFlowTool()
    configure_tool = ConfigureFlowTool()

    step1 = await start_tool.async_call(
        hass,
        llm.ToolInput(start_tool.name, {"domain": "random"}),
        llm_context,
    )
    assert step1.error is False
    assert isinstance(step1_res := step1.data["result"], dict)
    assert isinstance(flow_id := step1_res["flow_id"], str)
    assert step1_res["type"] == "menu"
    assert step1_res["step_id"] == "user"
    assert isinstance(menu_opts := step1_res["menu_options"], dict)
    assert "sensor" in menu_opts

    inspected = await configure_tool.async_call(
        hass,
        llm.ToolInput(configure_tool.name, {"flow_id": flow_id}),
        llm_context,
    )
    assert inspected.error is False
    assert isinstance(inspected_res := inspected.data["result"], dict)
    assert inspected_res["type"] == "menu"

    both_err = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "user_input": {}, "next_step_id": "sensor"},
        ),
        llm_context,
    )
    assert both_err == llm.ToolResult(
        data={"error": "Cannot specify both 'user_input' and 'next_step_id'."},
        error=True,
    )

    nested_next_err = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "user_input": {"next_step_id": "sensor"}},
        ),
        llm_context,
    )
    assert nested_next_err == llm.ToolResult(
        data={
            "error": (
                "Use the 'next_step_id' parameter instead of 'user_input' "
                "to select a menu option."
            )
        },
        error=True,
    )

    wrong_param_menu = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "user_input": {}},
        ),
        llm_context,
    )
    assert wrong_param_menu == llm.ToolResult(
        data={
            "error": (
                "Current step is a 'menu' step; pass the chosen option in "
                "'next_step_id' instead of 'user_input'."
            )
        },
        error=True,
    )

    invalid_menu_opt = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "next_step_id": "not_an_option"},
        ),
        llm_context,
    )
    assert invalid_menu_opt.error is True
    assert "next_step_id" in str(invalid_menu_opt.data["error"])

    step2 = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "next_step_id": "sensor"},
        ),
        llm_context,
    )
    assert step2.error is False
    assert isinstance(step2_res := step2.data["result"], dict)
    assert step2_res["type"] == "form"
    assert step2_res["step_id"] == "sensor"
    assert isinstance(fields := step2_res["fields"], list)
    field_names = [f["name"] for f in fields]
    assert "name" in field_names
    assert "minimum" in field_names
    assert "maximum" in field_names

    wrong_param_form = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "next_step_id": "sensor"},
        ),
        llm_context,
    )
    assert wrong_param_form == llm.ToolResult(
        data={
            "error": (
                "Current step is a 'form' step; pass field values in "
                "'user_input' instead of 'next_step_id'."
            )
        },
        error=True,
    )

    invalid_step = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {"flow_id": flow_id, "user_input": {"minimum": "not_an_int"}},
        ),
        llm_context,
    )
    assert invalid_step.error is True
    assert "minimum" in str(invalid_step.data["error"])

    step3 = await configure_tool.async_call(
        hass,
        llm.ToolInput(
            configure_tool.name,
            {
                "flow_id": flow_id,
                "user_input": {
                    "name": "Test Random Sensor",
                    "minimum": 10,
                    "maximum": 50,
                },
            },
        ),
        llm_context,
    )
    await hass.async_block_till_done()
    assert step3.error is False
    assert isinstance(step3_res := step3.data["result"], dict)
    assert step3_res["type"] == "create_entry"
    assert step3_res["title"] == "Test Random Sensor"
    assert isinstance(created_entry_id := step3_res["entry_id"], str)
    assert created_entry_id.startswith("random:")
    random_entries = hass.config_entries.async_entries("random")
    assert len(random_entries) == 1
    assert created_entry_id == f"random:{random_entries[0].entry_id[-4:]}"


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
async def test_config_flow_sections_selectors_and_progress(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
) -> None:
    """Test formatting form sections, select options, errors, and show_progress steps."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    translations: dict[str, dict[str, str]] = {
        "config": {
            f"component.{TEST_DOMAIN}.config.step.user.title": "Connect {device}",
            f"component.{TEST_DOMAIN}.config.step.user.description": "Configure {device}",
            f"component.{TEST_DOMAIN}.config.step.user.data.host": "Host address",
            f"component.{TEST_DOMAIN}.config.step.user.data_description.host": "IP or hostname",
            f"component.{TEST_DOMAIN}.config.step.user.sections.advanced.name": "Advanced settings",
            f"component.{TEST_DOMAIN}.config.step.user.sections.advanced.description": "Extra options",
            f"component.{TEST_DOMAIN}.config.step.user.sections.advanced.data.debug": "Enable debug",
            f"component.{TEST_DOMAIN}.config.error.cannot_connect": "Cannot reach {device}",
            f"component.{TEST_DOMAIN}.config.step.pairing.title": "Pairing {device}",
            f"component.{TEST_DOMAIN}.config.progress.wait_for_button": "Press button on {device}",
            f"component.{TEST_DOMAIN}.config.create_entry.default": "Created {device}",
        },
        "selector": {
            f"component.{TEST_DOMAIN}.selector.host_choice.options.auto": "Auto-discover",
            f"component.{TEST_DOMAIN}.selector.mode_choice.options.fast": "Fast mode",
        },
        "title": {
            f"component.{TEST_DOMAIN}.title": "Test Integration",
        },
    }

    async def _get_trans(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Any = None,
        config_flow: bool | None = None,
    ) -> dict[str, str]:
        return translations.get(category, {})

    progress_event = asyncio.Event()
    pairing_task: asyncio.Task[bool] | None = None
    pairing_calls = 0

    class RichConfigFlow(ConfigFlow):
        """Test config flow exercising sections, selectors, and progress steps."""

        VERSION = 1

        @override
        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            schema = self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required("host"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["auto", "manual"],
                                translation_key="host_choice",
                            )
                        ),
                        probatio.Optional("mode"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value="fast", label="Fallback Fast"
                                    ),
                                    selector.SelectOptionDict(
                                        value="slow", label="Slow mode"
                                    ),
                                ],
                                translation_key="mode_choice",
                            )
                        ),
                        probatio.Required("advanced"): data_entry_flow.section(
                            probatio.Schema({probatio.Optional("debug"): bool}),
                            {"collapsed": True},
                        ),
                    }
                ),
                {"host": "auto", "mode": None},
            )
            if user_input is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    description_placeholders={"device": "Bridge"},
                    last_step=False,
                )
            if user_input["host"] == "manual":
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    errors={"base": "cannot_connect"},
                    description_placeholders={"device": "Bridge"},
                    last_step=False,
                )
            return await self.async_step_pairing()

        async def async_step_pairing(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            nonlocal pairing_task, pairing_calls
            pairing_calls += 1
            if pairing_task is None:
                pairing_task = hass.async_create_task(progress_event.wait())
            if not pairing_task.done():
                return self.async_show_progress(
                    step_id="pairing",
                    progress_action="wait_for_button",
                    description_placeholders={"device": "Bridge"},
                    progress_task=pairing_task,
                )
            return self.async_show_progress_done(next_step_id="finish")

        async def async_step_finish(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_create_entry(
                title="Bridge",
                data={},
                description_placeholders={"device": "Bridge"},
            )

    with (
        mock_config_flow(TEST_DOMAIN, RichConfigFlow),
        patch(
            "homeassistant.components.config.llm.translation.async_get_translations",
            side_effect=_get_trans,
        ),
    ):
        start_tool = StartFlowTool()
        configure_tool = ConfigureFlowTool()

        step1 = await start_tool.async_call(
            hass,
            llm.ToolInput(start_tool.name, {"domain": TEST_DOMAIN}),
            llm_context,
        )
        assert step1.error is False
        assert isinstance(res1 := step1.data["result"], dict)
        flow_id = str(res1["flow_id"])
        assert flow_id.startswith(f"{TEST_DOMAIN}:")
        assert res1["title"] == "Connect Bridge"
        assert res1["description"] == "Configure Bridge"
        assert res1["last_step"] is False
        assert isinstance(fields := res1["fields"], list)
        assert isinstance(host_field := fields[0], dict)
        assert host_field["label"] == "Host address"
        assert host_field["description"] == "IP or hostname"
        assert host_field["suggested_value"] == "auto"
        assert host_field["selector"]["select"]["options"] == ["auto", "manual"]
        assert isinstance(mode_field := fields[1], dict)
        assert "suggested_value" not in mode_field
        assert mode_field["selector"]["select"]["options"] == [
            {"value": "fast", "label": "Fallback Fast"},
            {"value": "slow", "label": "Slow mode"},
        ]
        assert isinstance(sec_field := fields[2], dict)
        assert sec_field["type"] == "expandable"
        assert sec_field["label"] == "Advanced settings"
        assert sec_field["description"] == "Extra options"
        assert sec_field["schema"][0]["label"] == "Enable debug"

        err_step = await configure_tool.async_call(
            hass,
            llm.ToolInput(
                configure_tool.name,
                {
                    "flow_id": flow_id,
                    "user_input": {"host": "manual", "advanced": {}},
                },
            ),
            llm_context,
        )
        assert err_step.error is False
        assert isinstance(err_res := err_step.data["result"], dict)
        assert err_res["errors"] == {"base": "Cannot reach Bridge"}

        prog_step = await configure_tool.async_call(
            hass,
            llm.ToolInput(
                configure_tool.name,
                {
                    "flow_id": flow_id,
                    "user_input": {"host": "auto", "advanced": {"debug": True}},
                },
            ),
            llm_context,
        )
        assert prog_step.error is False
        assert isinstance(prog_res := prog_step.data["result"], dict)
        assert prog_res["type"] == "progress"
        assert prog_res["step_id"] == "pairing"
        assert prog_res["progress_action"] == "wait_for_button"
        assert prog_res["title"] == "Pairing Bridge"
        assert prog_res["description"] == "Press button on Bridge"
        assert pairing_calls == 1

        # Polling while progress_task is still running should not re-invoke async_step_pairing
        poll_step = await configure_tool.async_call(
            hass,
            llm.ToolInput(configure_tool.name, {"flow_id": flow_id}),
            llm_context,
        )
        assert poll_step == prog_step
        assert pairing_calls == 1

        reject_input_on_progress = await configure_tool.async_call(
            hass,
            llm.ToolInput(
                configure_tool.name,
                {"flow_id": flow_id, "user_input": {}},
            ),
            llm_context,
        )
        assert reject_input_on_progress == llm.ToolResult(
            data={
                "error": ("Current step has type 'progress' and does not accept input.")
            },
            error=True,
        )

        progress_event.set()
        await asyncio.sleep(0)
        done_step = await configure_tool.async_call(
            hass,
            llm.ToolInput(configure_tool.name, {"flow_id": flow_id}),
            llm_context,
        )
        await hass.async_block_till_done()
        assert done_step.error is False
        assert isinstance(done_res := done_step.data["result"], dict)
        assert done_res["type"] == "create_entry"
        assert done_res["title"] == "Bridge"
        assert done_res["description"] == "Created Bridge"


async def test_abort_flow_and_error_cases(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test aborting a flow and handling start_flow / configure_flow error cases."""
    start_tool = StartFlowTool()
    configure_tool = ConfigureFlowTool()

    err_unknown = await start_tool.async_call(
        hass,
        llm.ToolInput(start_tool.name, {"domain": "nonexistent_domain"}),
        llm_context,
    )
    assert err_unknown == llm.ToolResult(
        data={
            "error": (
                "Integration 'nonexistent_domain' does not exist or does not "
                "support config flows."
            )
        },
        error=True,
    )

    with patch.object(
        hass.config_entries.flow,
        "async_init",
        AsyncMock(side_effect=DependencyError(["mqtt", "http"])),
    ):
        dep_err = await start_tool.async_call(
            hass,
            llm.ToolInput(start_tool.name, {"domain": TEST_DOMAIN}),
            llm_context,
        )
    assert dep_err == llm.ToolResult(
        data={"error": "Failed dependencies: mqtt, http"},
        error=True,
    )

    err_unknown_flow = await configure_tool.async_call(
        hass,
        llm.ToolInput(configure_tool.name, {"flow_id": "unknown_flow"}),
        llm_context,
    )
    assert err_unknown_flow == llm.ToolResult(
        data={"error": "Flow 'unknown_flow' not found."},
        error=True,
    )

    err_unmatched_suffix = await configure_tool.async_call(
        hass,
        llm.ToolInput(configure_tool.name, {"flow_id": "random:9999"}),
        llm_context,
    )
    assert err_unmatched_suffix == llm.ToolResult(
        data={"error": "Flow 'random:9999' not found."},
        error=True,
    )

    step1 = await start_tool.async_call(
        hass,
        llm.ToolInput(start_tool.name, {"domain": "random"}),
        llm_context,
    )
    assert isinstance(step1_res := step1.data["result"], dict)
    assert isinstance(flow_id := step1_res["flow_id"], str)
    assert flow_id.startswith("random:")

    aborted = await configure_tool.async_call(
        hass,
        llm.ToolInput(configure_tool.name, {"flow_id": flow_id, "abort": True}),
        llm_context,
    )
    assert aborted == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id,
                "type": "abort",
                "reason": "aborted",
            }
        }
    )

    after_abort = await configure_tool.async_call(
        hass,
        llm.ToolInput(configure_tool.name, {"flow_id": flow_id}),
        llm_context,
    )
    assert after_abort.error is True

    MockConfigEntry(domain="sun", title="Sun").add_to_hass(hass)
    single_abort = await start_tool.async_call(
        hass,
        llm.ToolInput(start_tool.name, {"domain": "sun"}),
        llm_context,
    )
    assert single_abort.error is False
    assert isinstance(abort_res := single_abort.data["result"], dict)
    assert abort_res["type"] == "abort"
    assert abort_res["reason"] == "single_instance_allowed"
    assert (
        abort_res["description"]
        == "Already configured. Only a single configuration is possible."
    )


class _BaseOAuthTestFlow(ConfigFlow):
    """Base test flow providing auth and pick_implementation step methods."""

    VERSION = 1

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_external_step(
            step_id="auth", url="https://example.com/oauth/authorize"
        )

    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_form(step_id="pick_implementation")


async def _step_external(flow: _BaseOAuthTestFlow) -> ConfigFlowResult:
    """Return an external OAuth step."""
    return await flow.async_step_auth()


async def _step_pick_implementation(flow: _BaseOAuthTestFlow) -> ConfigFlowResult:
    """Return a pick_implementation form step."""
    return await flow.async_step_pick_implementation()


async def _step_missing_credentials(flow: _BaseOAuthTestFlow) -> ConfigFlowResult:
    """Return a missing_credentials abort step."""
    return flow.async_abort(reason="missing_credentials")


async def _step_redirect_runtime_error(flow: _BaseOAuthTestFlow) -> ConfigFlowResult:
    """Raise redirect-context RuntimeError via async_get_redirect_uri."""
    url = config_entry_oauth2_flow.async_get_redirect_uri(flow.hass)
    return flow.async_external_step(step_id="auth", url=url)


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
@pytest.mark.parametrize(
    "step_action",
    [
        pytest.param(_step_external, id="external_step"),
        pytest.param(_step_pick_implementation, id="pick_implementation"),
        pytest.param(_step_missing_credentials, id="missing_credentials"),
        pytest.param(_step_redirect_runtime_error, id="redirect_runtime_error"),
    ],
)
async def test_oauth_and_external_step_new_flow(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    step_action: Callable[[_BaseOAuthTestFlow], Coroutine[Any, Any, ConfigFlowResult]],
) -> None:
    """Test new user flows hitting OAuth/external steps abort cleanly and return a frontend URL."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    class OAuthUserFlow(_BaseOAuthTestFlow):
        """Test user config flow delegating to step_action."""

        @override
        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return await step_action(self)

    with mock_config_flow(TEST_DOMAIN, OAuthUserFlow):
        other_flow = OAuthUserFlow()
        other_flow.hass = hass
        other_flow.handler = TEST_DOMAIN
        other_flow.flow_id = "01J00000000000000000009999"
        other_flow.context = {"source": config_entries.SOURCE_ZEROCONF}
        hass.config_entries.flow._async_add_flow_progress(other_flow)

        start_tool = StartFlowTool()
        res = await start_tool.async_call(
            hass,
            llm.ToolInput(start_tool.name, {"domain": TEST_DOMAIN}),
            llm_context,
        )
        assert res.error is True
        assert (
            res.data["frontend_url"]
            == f"/config/integrations/dashboard/add?domain={TEST_DOMAIN}"
        )
        remaining = hass.config_entries.flow.async_progress_by_handler(
            TEST_DOMAIN, include_uninitialized=True
        )
        assert [flw["flow_id"] for flw in remaining] == [other_flow.flow_id]
        hass.config_entries.flow.async_abort(other_flow.flow_id)


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
@pytest.mark.parametrize(
    "step_action",
    [
        pytest.param(_step_external, id="external_step"),
        pytest.param(_step_redirect_runtime_error, id="redirect_runtime_error"),
    ],
)
async def test_oauth_and_external_step_on_configure_step(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    step_action: Callable[[_BaseOAuthTestFlow], Coroutine[Any, Any, ConfigFlowResult]],
) -> None:
    """Test flows hitting OAuth/external steps on step 2 abort cleanly and return a frontend URL."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    class TwoStepOAuthFlow(_BaseOAuthTestFlow):
        """Test flow with a form step followed by an OAuth step."""

        @override
        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            if user_input is not None:
                return await step_action(self)
            return self.async_show_form(step_id="user")

    with mock_config_flow(TEST_DOMAIN, TwoStepOAuthFlow):
        start_tool = StartFlowTool()
        configure_tool = ConfigureFlowTool()
        init_res = await start_tool.async_call(
            hass,
            llm.ToolInput(start_tool.name, {"domain": TEST_DOMAIN}),
            llm_context,
        )
        assert init_res.error is False
        assert isinstance(step1 := init_res.data["result"], dict)

        with (
            patch.object(
                hass.config_entries.flow,
                "async_init",
                AsyncMock(side_effect=RuntimeError("unexpected error")),
            ),
            pytest.raises(RuntimeError, match="unexpected error"),
        ):
            await start_tool.async_call(
                hass,
                llm.ToolInput(start_tool.name, {"domain": TEST_DOMAIN}),
                llm_context,
            )

        with (
            patch.object(
                hass.config_entries.flow,
                "async_configure",
                AsyncMock(side_effect=RuntimeError("unexpected error")),
            ),
            pytest.raises(RuntimeError, match="unexpected error"),
        ):
            await configure_tool.async_call(
                hass,
                llm.ToolInput(
                    configure_tool.name,
                    {"flow_id": step1["flow_id"], "user_input": {}},
                ),
                llm_context,
            )

        step2_res = await configure_tool.async_call(
            hass,
            llm.ToolInput(
                configure_tool.name,
                {"flow_id": step1["flow_id"], "user_input": {}},
            ),
            llm_context,
        )
        assert step2_res.error is True
        assert (
            step2_res.data["frontend_url"]
            == f"/config/integrations/dashboard/add?domain={TEST_DOMAIN}"
        )
        assert (
            hass.config_entries.flow.async_progress_by_handler(
                TEST_DOMAIN, include_uninitialized=True
            )
            == []
        )


@pytest.mark.parametrize(
    ("tool", "tool_args"),
    [
        pytest.param(
            StartFlowTool(),
            {},
            id="start_flow_missing_domain",
        ),
        pytest.param(
            StartFlowTool(),
            {"domain": "   "},
            id="start_flow_whitespace_domain",
        ),
        pytest.param(
            ConfigureFlowTool(),
            {"flow_id": ""},
            id="configure_flow_empty_id",
        ),
        pytest.param(
            ConfigureFlowTool(),
            {"flow_id": "abc", "next_step_id": "   "},
            id="configure_flow_whitespace_next_step_id",
        ),
    ],
)
async def test_flow_tools_invalid_parameters(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool: llm.Tool,
    tool_args: dict[str, Any],
) -> None:
    """Test invalid arguments are rejected by StartFlowTool and ConfigureFlowTool."""
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)
