"""Tests for the config LLM tools."""

import asyncio
from collections.abc import Callable, Coroutine, Generator
from typing import Any, override
from unittest.mock import AsyncMock, Mock, patch

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
    GetCoreConfigTool,
    GetFlowsInProgressTool,
    ReloadConfigEntryTool,
    SearchIntegrationsTool,
    StartFlowTool,
    UpdateCoreConfigTool,
    async_get_tools,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, DependencyError
from homeassistant.helpers import config_entry_oauth2_flow, llm, selector, translation
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


@pytest.fixture
async def llm_api(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    llm_context: llm.LLMContext,
) -> llm.APIInstance:
    """Set up config and llm components and return the Home Assistant LLM API."""
    assert await async_setup_component(hass, config_component.DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)
    return await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)


@pytest.fixture
def mock_translations(request: pytest.FixtureRequest) -> Generator[None]:
    """Overlay category-keyed dicts onto async_get_translations in config.llm."""
    translations: dict[str, dict[str, str]] = request.param
    real_get_translations = translation.async_get_translations

    async def _get_translations(
        hass: HomeAssistant, language: str, category: str, *args: Any
    ) -> dict[str, str]:
        base = await real_get_translations(hass, language, category, *args)
        return base | translations.get(category, {})

    with patch(
        "homeassistant.components.config.llm.translation.async_get_translations",
        side_effect=_get_translations,
    ):
        yield


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
        "config__get_flows_in_progress",
        "config__start_flow",
        "config__configure_flow",
        "config__get_core_config",
        "config__update_core_config",
    ]
    assert ha_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that tool schemas can be exported for LLM clients."""
    tools = [
        GetConfigEntriesTool(),
        ReloadConfigEntryTool(),
        SearchIntegrationsTool(),
        GetFlowsInProgressTool(),
        StartFlowTool(),
        ConfigureFlowTool(),
        UpdateCoreConfigTool(),
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

    flows_tool = next(
        tool for tool in api.tools if tool.name == "config__get_flows_in_progress"
    )
    assert flows_tool.integration == config_component.DOMAIN
    assert flows_tool.annotations == llm.ToolAnnotations(
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
            {"query": "random"},
            [{"domain": "random", "name": "Random", "categories": ["helpers"]}],
            {"random"},
            id="helper_exact",
        ),
        pytest.param(
            {"query": "sun"},
            [
                {
                    "domain": "sun",
                    "name": "Sun",
                    "categories": ["weather_alerts.forecasts"],
                }
            ],
            {"sun"},
            id="integration_exact",
        ),
        pytest.param(
            {"query": "Times of the Day"},
            [
                {
                    "domain": "tod",
                    "name": "Times of the Day Sensor",
                    "categories": ["helpers.calculate_value"],
                }
            ],
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
            {"query": "yale bluetooth"},
            [
                {
                    "domain": "yalexs_ble",
                    "name": "Yale Access Bluetooth",
                    "categories": ["security_safety.locks_access"],
                }
            ],
            {"yalexs_ble"},
            id="multi_word_deduplicated",
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
        pytest.param(
            {"category": "pets"},
            [],
            {"litterrobot", "surepetcare", "tractive"},
            id="category_only",
        ),
        pytest.param(
            {"query": "tibber", "category": "energy"},
            [
                {
                    "domain": "tibber",
                    "name": "Tibber",
                    "categories": ["energy.energy_prices", "energy.meters_monitoring"],
                }
            ],
            {"tibber"},
            id="query_and_category_includes_subcategories",
        ),
        pytest.param(
            {"query": "hue", "category": "energy"},
            [],
            set(),
            id="query_and_category_no_match",
        ),
        pytest.param(
            {"category": "helpers", "query": "meter"},
            [],
            {"utility_meter"},
            id="helper_by_category",
        ),
        pytest.param(
            {"category": "helpers", "query": "workday"},
            [],
            {"workday"},
            id="helpers_category_includes_integrations",
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
    domains = [item["domain"] for item in items if isinstance(item, dict)]
    assert len(domains) == len(set(domains))
    assert expected_domains <= set(domains)
    assert bool(domains) is bool(expected_domains)
    if category := tool_args.get("category"):
        for item in items:
            assert isinstance(item, dict)
            assert isinstance(categories := item["categories"], list)
            assert any(str(cat).partition(".")[0] == category for cat in categories)


async def test_search_integrations_pagination(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
) -> None:
    """Test paging through the results with offset and next_offset."""
    tool = SearchIntegrationsTool()
    domains: list[str] = []
    offset = 0
    pages = 0
    while True:
        res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"category": "energy", "offset": offset}),
            llm_context,
        )
        assert res.error is False
        assert isinstance(items := res.data["result"], list)
        assert isinstance(total := res.data["total"], int)
        domains.extend(item["domain"] for item in items if isinstance(item, dict))
        pages += 1
        if "next_offset" not in res.data:
            break
        assert len(items) == 15
        assert isinstance(next_offset := res.data["next_offset"], int)
        offset = next_offset

    assert pages > 1
    assert len(domains) == total
    assert len(set(domains)) == total


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({}, id="missing_query_and_category"),
        pytest.param({"category": ""}, id="empty_category"),
        pytest.param({"category": "unknown"}, id="unknown_category"),
        pytest.param({"category": "energy.energy_prices"}, id="subcategory"),
        pytest.param({"query": ""}, id="empty_query"),
        pytest.param({"query": "   "}, id="whitespace_query"),
        pytest.param({"query": "hue", "offset": -1}, id="negative_offset"),
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


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
async def test_get_flows_in_progress(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
) -> None:
    """Test listing pending discovery and reauth flows with title resolution."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    translations: dict[str, dict[str, str]] = {
        "config": {
            f"component.{TEST_DOMAIN}.config.flow_title": "{model} ({host})",
        },
        "title": {
            f"component.{TEST_DOMAIN}.title": "Test Integration Title",
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

    class DiscoveryFlow(ConfigFlow):
        """Test flow supporting zeroconf, ssdp, dhcp, reauth, reconfigure, and user."""

        VERSION = 1

        @override
        async def async_step_zeroconf(
            self, discovery_info: Any = None
        ) -> ConfigFlowResult:
            self.context["title_placeholders"] = {
                "model": "Hue Bridge",
                "host": "192.168.1.2",
            }
            return await self.async_step_confirm()

        @override
        async def async_step_ssdp(self, discovery_info: Any = None) -> ConfigFlowResult:
            self.context["title_placeholders"] = {"host": "192.168.1.3", "name": ""}
            return await self.async_step_confirm()

        @override
        async def async_step_dhcp(self, discovery_info: Any = None) -> ConfigFlowResult:
            return await self.async_step_confirm()

        async def async_step_confirm(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_show_form(step_id="confirm")

        async def async_step_reauth(
            self, entry_data: dict[str, Any]
        ) -> ConfigFlowResult:
            return await self.async_step_confirm()

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_show_form(step_id="reconfigure")

        @override
        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_show_form(step_id="user")

    with (
        mock_config_flow(TEST_DOMAIN, DiscoveryFlow),
        patch(
            "homeassistant.components.config.llm.translation.async_get_translations",
            side_effect=_get_trans,
        ),
    ):
        entry = MockConfigEntry(
            domain=TEST_DOMAIN,
            title="Existing Entry",
            entry_id="01J00000000000000000001001",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await entry.start_reconfigure_flow(hass)
        disc_result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}
        )
        ssdp_result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_SSDP}
        )
        dhcp_result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_DHCP}
        )
        reauth_result = await entry.start_reauth_flow(hass)

        expected_flows = [
            {
                "flow_id": f"{TEST_DOMAIN}:{disc_result['flow_id'][-4:]}",
                "domain": TEST_DOMAIN,
                "source": "zeroconf",
                "title": "Hue Bridge (192.168.1.2)",
                "step_id": "confirm",
            },
            {
                "flow_id": f"{TEST_DOMAIN}:{ssdp_result['flow_id'][-4:]}",
                "domain": TEST_DOMAIN,
                "source": "ssdp",
                "title": "Test Integration Title",
                "step_id": "confirm",
            },
            {
                "flow_id": f"{TEST_DOMAIN}:{dhcp_result['flow_id'][-4:]}",
                "domain": TEST_DOMAIN,
                "source": "dhcp",
                "title": "Test Integration Title",
                "step_id": "confirm",
            },
            {
                "flow_id": f"{TEST_DOMAIN}:{reauth_result['flow_id'][-4:]}",
                "domain": TEST_DOMAIN,
                "source": "reauth",
                "title": "Existing Entry",
                "step_id": "confirm",
                "entry_id": f"{TEST_DOMAIN}:1001",
            },
        ]

        tool = GetFlowsInProgressTool()
        all_res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {}),
            llm_context,
        )
        assert all_res == llm.ToolResult(data={"result": expected_flows})

        filtered_res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"domain": f"  {TEST_DOMAIN.upper()}  "}),
            llm_context,
        )
        assert filtered_res == llm.ToolResult(data={"result": expected_flows})

        empty_res = await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"domain": "other_domain"}),
            llm_context,
        )
        assert empty_res == llm.ToolResult(data={"result": []})


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_SSDP]
)
@pytest.mark.parametrize(
    "step_action",
    [
        pytest.param(_step_external, id="external_step"),
        pytest.param(_step_pick_implementation, id="pick_implementation"),
        pytest.param(_step_missing_credentials, id="missing_credentials"),
        pytest.param(_step_redirect_runtime_error, id="redirect_runtime_error"),
    ],
)
async def test_discovery_oauth_handoff(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    source: str,
    step_action: Callable[[_BaseOAuthTestFlow], Coroutine[Any, Any, ConfigFlowResult]],
) -> None:
    """Test discovered devices open browser setup when authentication is required."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    class DiscoveryOAuthFlow(_BaseOAuthTestFlow):
        """Discovery flow with a confirmation before authentication."""

        @override
        async def async_step_zeroconf(self, discovery_info: Any) -> ConfigFlowResult:
            return await self.async_step_confirm()

        @override
        async def async_step_ssdp(self, discovery_info: Any) -> ConfigFlowResult:
            return await self.async_step_confirm()

        async def async_step_confirm(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            if user_input is not None:
                return await step_action(self)
            return self.async_show_form(step_id="confirm")

    with mock_config_flow(TEST_DOMAIN, DiscoveryOAuthFlow):
        started = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": source}
        )
        result = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {
                    "flow_id": f"{TEST_DOMAIN}:{started['flow_id'][-4:]}",
                    "user_input": {},
                },
            )
        )

    assert result.error is True
    assert (
        result.data["frontend_url"]
        == f"/config/integrations/dashboard/add?domain={TEST_DOMAIN}"
    )
    assert hass.config_entries.flow.async_progress_by_handler(TEST_DOMAIN) == []


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        pytest.param(
            "config__start_flow",
            {"flow_type": "invalid"},
            id="start_flow_invalid_flow_type",
        ),
        pytest.param(
            "config__get_flows_in_progress",
            {"domain": ""},
            id="get_flows_in_progress_empty_domain",
        ),
        pytest.param(
            "config__get_flows_in_progress",
            {"domain": "   "},
            id="get_flows_in_progress_whitespace_domain",
        ),
        pytest.param(
            "config__start_flow",
            {"domain": "   "},
            id="start_flow_whitespace_domain",
        ),
        pytest.param(
            "config__start_flow",
            {"flow_type": "options", "entry_id": "   "},
            id="start_flow_whitespace_entry_id",
        ),
        pytest.param(
            "config__configure_flow",
            {"flow_id": ""},
            id="configure_flow_empty_id",
        ),
        pytest.param(
            "config__configure_flow",
            {"flow_id": "abc", "next_step_id": "   "},
            id="configure_flow_whitespace_next_step_id",
        ),
    ],
)
async def test_flow_tools_invalid_parameters(
    llm_api: llm.APIInstance,
    tool_name: str,
    tool_args: dict[str, Any],
) -> None:
    """Test invalid arguments are rejected by flow tools."""
    with pytest.raises(probatio.Invalid):
        await llm_api.async_call_tool(llm.ToolInput(tool_name, tool_args))


async def test_get_core_config(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting the core config."""
    tool = GetCoreConfigTool()
    res = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)
    assert res.error is False
    assert res.data == {
        "result": {
            "location_name": "test home",
            "latitude": hass.config.latitude,
            "longitude": hass.config.longitude,
            "elevation": 0,
            "radius": 100,
            "time_zone": "US/Pacific",
            "country": None,
            "currency": "EUR",
            "language": "en",
            "unit_system": "metric",
            "internal_url": None,
            "internal_url_in_use": None,
            "external_url": None,
            "external_url_in_use": None,
        }
    }


async def test_get_core_config_urls_in_use(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the URLs in use are the detected ones until a URL is set."""
    hass.config.api = Mock(use_ssl=False, port=8123, local_ip="192.168.1.10")
    tool = GetCoreConfigTool()
    res = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)
    result = res.data["result"]
    assert result["internal_url"] is None
    assert result["internal_url_in_use"] == "http://192.168.1.10:8123"
    assert result["external_url"] is None
    assert result["external_url_in_use"] is None

    await hass.config.async_update(
        internal_url="http://homeassistant.local:8123",
        external_url="https://example.com",
    )
    res = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)
    result = res.data["result"]
    assert result["internal_url"] == "http://homeassistant.local:8123"
    assert result["internal_url_in_use"] == "http://homeassistant.local:8123"
    assert result["external_url"] == "https://example.com"
    assert result["external_url_in_use"] == "https://example.com"


async def test_update_core_config(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test updating the core config."""
    tool = UpdateCoreConfigTool()
    res = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "location_name": "Home",
                "latitude": 52.37,
                "longitude": 4.89,
                "country": "NL",
                "time_zone": "Europe/Amsterdam",
                "unit_system": "us_customary",
                "external_url": "https://example.com",
            },
        ),
        llm_context,
    )
    assert res.error is False
    result = res.data["result"]
    assert result["location_name"] == "Home"
    assert result["latitude"] == 52.37
    assert result["longitude"] == 4.89
    assert result["country"] == "NL"
    assert result["time_zone"] == "Europe/Amsterdam"
    assert result["unit_system"] == "us_customary"
    assert result["external_url"] == "https://example.com"
    assert hass.config.country == "NL"
    assert hass.config.time_zone == "Europe/Amsterdam"


@pytest.mark.parametrize(
    ("unit_system", "updates_units"),
    [("us_customary", True), ("metric", False), (None, False)],
)
async def test_update_core_config_updates_units(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    unit_system: str | None,
    updates_units: bool,
) -> None:
    """Test that only a new unit system changes the units of the sensors."""
    tool_args: dict[str, Any] = {"location_name": "Home"}
    if unit_system:
        tool_args["unit_system"] = unit_system
    tool = UpdateCoreConfigTool()
    with patch(
        "homeassistant.components.config.core.async_update_suggested_units"
    ) as mock_update_units:
        res = await tool.async_call(
            hass, llm.ToolInput(tool.name, tool_args), llm_context
        )
    assert res.error is False
    assert mock_update_units.called is updates_units


@pytest.mark.parametrize(
    ("tool_args", "error"),
    [
        pytest.param({"country": "XX"}, "Invalid input", id="country"),
        pytest.param({"currency": "XXX"}, "Invalid input", id="currency"),
        pytest.param({"latitude": 100}, "Invalid input", id="latitude"),
        pytest.param({"radius": -1}, "Invalid input", id="radius"),
        pytest.param(
            {"external_url": "https://example.com/path"},
            "Invalid input",
            id="url_with_path",
        ),
        pytest.param({"time_zone": "Mars/Base"}, "Received invalid time zone", id="tz"),
    ],
)
async def test_update_core_config_invalid(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: dict[str, Any],
    error: str,
) -> None:
    """Test that invalid values return an error and change nothing."""
    tool = UpdateCoreConfigTool()
    res = await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)
    assert res.error is True
    assert res.data["error"].startswith(error)
    assert hass.config.country is None
    assert hass.config.time_zone == "US/Pacific"


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({"location": "home"}, id="location"),
        pytest.param({"unit_system": "imperial"}, id="unit_system"),
    ],
)
async def test_update_core_config_invalid_args(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: dict[str, Any],
) -> None:
    """Test invalid arguments are rejected by UpdateCoreConfigTool."""
    tool = UpdateCoreConfigTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)


async def test_get_config_entries_flow_capabilities(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test GetConfigEntriesTool exposes supports_options and supports_reconfigure."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    class CapableOptionsFlow(OptionsFlow):
        """Options flow for capability test."""

        async def async_step_init(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_show_form(step_id="init")

    class CapableFlow(ConfigFlow):
        """Config flow supporting both options and reconfigure."""

        @staticmethod
        @callback
        @override
        def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
            return CapableOptionsFlow()

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return self.async_show_form(step_id="reconfigure")

    active = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Active",
        entry_id="01J00000000000000000002001",
        state=ConfigEntryState.LOADED,
    )
    active.add_to_hass(hass)
    errored = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Errored",
        entry_id="01J00000000000000000002004",
        state=ConfigEntryState.SETUP_ERROR,
    )
    errored.add_to_hass(hass)
    disabled = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Disabled",
        entry_id="01J00000000000000000002002",
        disabled_by=ConfigEntryDisabler.USER,
    )
    disabled.add_to_hass(hass)
    ignored = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Ignored",
        entry_id="01J00000000000000000002003",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored.add_to_hass(hass)

    with mock_config_flow(TEST_DOMAIN, CapableFlow):
        result = await llm_api.async_call_tool(
            llm.ToolInput("config__get_config_entries", {"domain": TEST_DOMAIN})
        )

    assert result == llm.ToolResult(
        data={
            "result": [
                {
                    "entry_id": f"{TEST_DOMAIN}:2001",
                    "domain": TEST_DOMAIN,
                    "title": "Active",
                    "state": "loaded",
                    "supports_options": True,
                    "supports_reconfigure": True,
                },
                {
                    "entry_id": f"{TEST_DOMAIN}:2004",
                    "domain": TEST_DOMAIN,
                    "title": "Errored",
                    "state": "setup_error",
                    "supports_reconfigure": True,
                },
                {
                    "entry_id": f"{TEST_DOMAIN}:2002",
                    "domain": TEST_DOMAIN,
                    "title": "Disabled",
                    "state": "not_loaded",
                    "disabled_by": "user",
                },
                {
                    "entry_id": f"{TEST_DOMAIN}:2003",
                    "domain": TEST_DOMAIN,
                    "title": "Ignored",
                    "state": "not_loaded",
                    "source": "ignore",
                },
            ]
        }
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.parametrize(
    "mock_translations",
    [
        {
            "options": {
                f"component.{TEST_DOMAIN}.options.step.init.title": "Sensor options",
                f"component.{TEST_DOMAIN}.options.step.init.data.minimum": "Minimum",
                f"component.{TEST_DOMAIN}.options.step.init.data.maximum": "Maximum",
            },
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains", "mock_translations")
async def test_options_flow_end_to_end(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test starting, inspecting, aborting, and completing an options flow."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Sensor",
        entry_id="01J00000000000000000002501",
        options={"minimum": 1, "maximum": 10},
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    class SensorOptionsFlow(OptionsFlow):
        """Mock options flow updating minimum and maximum."""

        async def async_step_init(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            if user_input is not None:
                return self.async_create_entry(data=user_input)
            schema = self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required("minimum"): int,
                        probatio.Required("maximum"): int,
                    }
                ),
                self.config_entry.options,
            )
            return self.async_show_form(step_id="init", data_schema=schema)

    class SensorConfigFlow(ConfigFlow):
        """Mock config flow with options support."""

        @staticmethod
        @callback
        @override
        def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
            return SensorOptionsFlow()

    short_entry_id = f"{TEST_DOMAIN}:2501"
    with mock_config_flow(TEST_DOMAIN, SensorConfigFlow):
        opt_start = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "options", "entry_id": short_entry_id},
            )
        )
        assert opt_start.error is False
        assert isinstance(opt_step := opt_start.data["result"], dict)
        opt_flow_id = opt_step["flow_id"]
        assert opt_flow_id.startswith(f"{TEST_DOMAIN}:")
        assert opt_step["type"] == "form"
        assert opt_step["step_id"] == "init"
        assert opt_step["title"] == "Sensor options"
        assert opt_step["fields"] == [
            {
                "name": "minimum",
                "required": True,
                "type": "integer",
                "suggested_value": 1,
                "label": "Minimum",
            },
            {
                "name": "maximum",
                "required": True,
                "type": "integer",
                "suggested_value": 10,
                "label": "Maximum",
            },
        ]

        inspected = await llm_api.async_call_tool(
            llm.ToolInput("config__configure_flow", {"flow_id": opt_flow_id})
        )
        assert inspected.error is False
        assert isinstance(inspected_res := inspected.data["result"], dict)
        assert inspected_res["step_id"] == "init"

        aborted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow", {"flow_id": opt_flow_id, "abort": True}
            )
        )
        assert aborted == llm.ToolResult(
            data={
                "result": {
                    "flow_id": opt_flow_id,
                    "type": "abort",
                    "reason": "aborted",
                }
            }
        )

        opt_start2 = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "options", "entry_id": short_entry_id},
            )
        )
        assert isinstance(opt_step2 := opt_start2.data["result"], dict)
        opt_done = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {
                    "flow_id": opt_step2["flow_id"],
                    "user_input": {"minimum": 5, "maximum": 25},
                },
            )
        )
        await hass.async_block_till_done()

    assert opt_done.error is False
    assert isinstance(opt_done_res := opt_done.data["result"], dict)
    assert opt_done_res["type"] == "create_entry"
    assert entry.options == {"minimum": 5, "maximum": 25}


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.parametrize(
    "mock_translations",
    [
        {
            "config": {
                f"component.{TEST_DOMAIN}.config.step.reconfigure.title": (
                    "Reconfigure bridge"
                ),
                f"component.{TEST_DOMAIN}.config.step.reconfigure.data.host": "Host",
                f"component.{TEST_DOMAIN}.config.error.cannot_connect": (
                    "Cannot connect"
                ),
            },
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains", "mock_translations")
async def test_reconfigure_flow(hass: HomeAssistant, llm_api: llm.APIInstance) -> None:
    """Test starting and completing a reconfigure flow with translations and validation."""
    mock_integration(
        hass,
        MockModule(TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Bridge",
        entry_id="01J00000000000000000003001",
        data={"host": "192.168.1.10"},
    )
    entry.add_to_hass(hass)

    class ReconfigureFlow(ConfigFlow):
        """Test flow supporting reconfigure."""

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            reconf_entry = self._get_reconfigure_entry()
            errors: dict[str, str] = {}
            if user_input is not None:
                if user_input["host"] == "bad":
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        reconf_entry,
                        data_updates={"host": user_input["host"]},
                    )
            schema = self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required("host"): str}),
                reconf_entry.data,
            )
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=schema,
                errors=errors,
            )

    with mock_config_flow(TEST_DOMAIN, ReconfigureFlow):
        started = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "reconfigure", "entry_id": f"{TEST_DOMAIN}:3001"},
            )
        )
        assert started.error is False
        assert isinstance(step := started.data["result"], dict)
        flow_id = step["flow_id"]
        assert step["title"] == "Reconfigure bridge"
        assert step["fields"] == [
            {
                "name": "host",
                "required": True,
                "type": "string",
                "suggested_value": "192.168.1.10",
                "label": "Host",
            }
        ]

        err_res = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": flow_id, "user_input": {"host": "bad"}},
            )
        )
        assert err_res.error is False
        assert isinstance(err_step := err_res.data["result"], dict)
        assert err_step["errors"] == {"base": "Cannot connect"}

        done = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": flow_id, "user_input": {"host": "192.168.1.20"}},
            )
        )
        await hass.async_block_till_done()

    assert done == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id,
                "type": "abort",
                "reason": "reconfigure_successful",
                "description": "Reconfiguration was successful",
            }
        }
    )
    assert entry.data == {"host": "192.168.1.20"}


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
async def test_options_flow_abort_fallback(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test options flow abort falls back to homeassistant.config.abort translations."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Entry",
        entry_id="01J00000000000000000004001",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    class AbortingOptionsFlow(OptionsFlow):
        """Options flow that shows a form then aborts with a shared homeassistant reason."""

        async def async_step_init(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            if user_input is not None:
                return self.async_abort(reason="already_in_progress")
            return self.async_show_form(step_id="init")

    class FlowWithOptions(ConfigFlow):
        """Config flow with options support."""

        @staticmethod
        @callback
        @override
        def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
            return AbortingOptionsFlow()

    with mock_config_flow(TEST_DOMAIN, FlowWithOptions):
        opt_started = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "options", "entry_id": f"{TEST_DOMAIN}:4001"},
            )
        )
        assert isinstance(opt_step := opt_started.data["result"], dict)
        aborted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": opt_step["flow_id"], "user_input": {}},
            )
        )

    assert aborted.error is False
    assert isinstance(aborted_res := aborted.data["result"], dict)
    assert aborted_res["type"] == "abort"
    assert aborted_res["reason"] == "already_in_progress"
    assert "description" in aborted_res


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
@pytest.mark.parametrize(
    "step_action",
    [
        pytest.param(_step_external, id="external_step"),
        pytest.param(_step_redirect_runtime_error, id="redirect_runtime_error"),
    ],
)
async def test_reconfigure_oauth_errors(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    step_action: Callable[[_BaseOAuthTestFlow], Coroutine[Any, Any, ConfigFlowResult]],
) -> None:
    """Test OAuth/external steps during reconfigure point to the existing integration page."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="OAuth Entry",
        entry_id="01J00000000000000000005001",
    )
    entry.add_to_hass(hass)

    class ReconfigureOAuthStartFlow(_BaseOAuthTestFlow):
        """Reconfigure flow hitting OAuth on step 1."""

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            return await step_action(self)

    class ReconfigureOAuthStep2Flow(_BaseOAuthTestFlow):
        """Reconfigure flow hitting OAuth on step 2."""

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            if user_input is not None:
                return await step_action(self)
            return self.async_show_form(step_id="reconfigure")

    expected_url = f"/config/integrations/integration/{TEST_DOMAIN}"

    with mock_config_flow(TEST_DOMAIN, ReconfigureOAuthStartFlow):
        res1 = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "reconfigure", "entry_id": f"{TEST_DOMAIN}:5001"},
            )
        )
        assert res1.error is True
        assert res1.data["frontend_url"] == expected_url

    with mock_config_flow(TEST_DOMAIN, ReconfigureOAuthStep2Flow):
        started = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {"flow_type": "reconfigure", "entry_id": f"{TEST_DOMAIN}:5001"},
            )
        )
        assert isinstance(step1 := started.data["result"], dict)
        res2 = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": step1["flow_id"], "user_input": {}},
            )
        )
        assert res2.error is True
        assert res2.data["frontend_url"] == expected_url


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    [[TEST_DOMAIN, "test_llm_unloaded"]],
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
@pytest.mark.parametrize(
    ("tool_args", "expected_error"),
    [
        pytest.param(
            {"domain": TEST_DOMAIN, "entry_id": f"{TEST_DOMAIN}:6001"},
            "Cannot specify both 'domain' and 'entry_id'.",
            id="both_domain_and_entry_id",
        ),
        pytest.param(
            {"entry_id": f"{TEST_DOMAIN}:6001"},
            "Specify 'flow_type' ('options', 'reconfigure', or 'subentry') when passing 'entry_id'.",
            id="entry_id_without_flow_type",
        ),
        pytest.param(
            {"domain": TEST_DOMAIN, "subentry_type": "agent"},
            "'subentry_type' and 'subentry_id' are only valid when flow_type is 'subentry' or 'reconfigure'.",
            id="subentry_type_with_config_flow",
        ),
        pytest.param(
            {
                "flow_type": "options",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_id": "agent:7001",
            },
            "'subentry_type' and 'subentry_id' are only valid when flow_type is 'subentry' or 'reconfigure'.",
            id="subentry_id_with_options_flow",
        ),
        pytest.param(
            {"flow_type": "subentry"},
            "'entry_id' is required when flow_type is 'subentry'.",
            id="missing_entry_id_for_subentry",
        ),
        pytest.param(
            {"flow_type": "subentry", "entry_id": f"{TEST_DOMAIN}:6001"},
            "'subentry_type' is required when starting a subentry flow.",
            id="missing_subentry_type",
        ),
        pytest.param(
            {
                "flow_type": "reconfigure",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_type": "agent",
            },
            "'subentry_id' is required when reconfiguring a subentry.",
            id="reconfigure_subentry_missing_id",
        ),
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_id": "invalid",
            },
            "Subentry 'invalid' not found.",
            id="malformed_subentry_id",
        ),
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_id": "agent:9999",
            },
            "Subentry 'agent:9999' not found.",
            id="unknown_subentry_id",
        ),
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_type": "other",
                "subentry_id": "agent:7001",
            },
            "Subentry 'agent:7001' does not match subentry_type 'other'.",
            id="mismatched_subentry_type",
        ),
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_type": "unsupported",
            },
            f"Config entry '{TEST_DOMAIN}:6001' does not support subentry type 'unsupported'.",
            id="unsupported_subentry_type",
        ),
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:6001",
                "subentry_id": "agent:7001",
            },
            "Subentry 'agent:7001' does not support reconfigure.",
            id="unsupported_subentry_reconfigure",
        ),
        pytest.param(
            {},
            "'domain' is required when flow_type is 'config'.",
            id="missing_domain_for_config",
        ),
        pytest.param(
            {"flow_type": "options"},
            "'entry_id' is required when flow_type is 'options'.",
            id="missing_entry_id_for_options",
        ),
        pytest.param(
            {"flow_type": "reconfigure"},
            "'entry_id' is required when flow_type is 'reconfigure'.",
            id="missing_entry_id_for_reconfigure",
        ),
        pytest.param(
            {"flow_type": "options", "entry_id": f"{TEST_DOMAIN}:9999"},
            f"Config entry '{TEST_DOMAIN}:9999' not found.",
            id="unknown_entry_id",
        ),
        pytest.param(
            {"flow_type": "options", "entry_id": f"{TEST_DOMAIN}:6002"},
            f"Config entry '{TEST_DOMAIN}:6002' cannot be configured because it is disabled.",
            id="disabled_entry",
        ),
        pytest.param(
            {"flow_type": "reconfigure", "entry_id": f"{TEST_DOMAIN}:6003"},
            f"Config entry '{TEST_DOMAIN}:6003' cannot be configured because it is ignored.",
            id="ignored_entry",
        ),
        pytest.param(
            {"flow_type": "options", "entry_id": f"{TEST_DOMAIN}:6005"},
            (
                f"Config entry '{TEST_DOMAIN}:6005' must be loaded to configure "
                "options (current state: 'setup_error')."
            ),
            id="not_loaded_options_entry",
        ),
        pytest.param(
            {"flow_type": "options", "entry_id": "test_llm_unloaded:6004"},
            "Config entry 'test_llm_unloaded:6004' does not support options.",
            id="unsupported_options_unloaded_handler",
        ),
        pytest.param(
            {"flow_type": "options", "entry_id": f"{TEST_DOMAIN}:6001"},
            f"Config entry '{TEST_DOMAIN}:6001' does not support options.",
            id="unsupported_options_loaded_handler",
        ),
        pytest.param(
            {"flow_type": "reconfigure", "entry_id": f"{TEST_DOMAIN}:6001"},
            f"Config entry '{TEST_DOMAIN}:6001' does not support reconfigure.",
            id="unsupported_reconfigure",
        ),
    ],
)
async def test_start_flow_entry_validation_errors(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    tool_args: dict[str, Any],
    expected_error: str,
) -> None:
    """Test StartFlowTool parameter and entry capability validation errors."""
    unloaded_domain = "test_llm_unloaded"
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)
    mock_integration(hass, MockModule(unloaded_domain))
    mock_platform(hass, f"{unloaded_domain}.config_flow", None)

    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Basic",
        entry_id="01J00000000000000000006001",
        state=ConfigEntryState.LOADED,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_id="01J00000000000000000007001",
                subentry_type="agent",
                title="Basic Agent",
                unique_id=None,
            )
        ],
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Disabled",
        entry_id="01J00000000000000000006002",
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Ignored",
        entry_id="01J00000000000000000006003",
        source=config_entries.SOURCE_IGNORE,
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=unloaded_domain,
        title="Unloaded Handler",
        entry_id="01J00000000000000000006004",
        state=ConfigEntryState.LOADED,
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Setup Error",
        entry_id="01J00000000000000000006005",
        state=ConfigEntryState.SETUP_ERROR,
    ).add_to_hass(hass)

    class NoReconfigureSubentryFlow(ConfigSubentryFlow):
        """Subentry flow without reconfigure support."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_show_form(step_id="user")

    class BasicFlow(ConfigFlow):
        """Basic flow without options or reconfigure."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"agent": NoReconfigureSubentryFlow}

    with mock_config_flow(TEST_DOMAIN, BasicFlow):
        res = await llm_api.async_call_tool(
            llm.ToolInput("config__start_flow", tool_args)
        )

    assert res == llm.ToolResult(data={"error": expected_error}, error=True)


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
async def test_get_config_entries_subentries(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test GetConfigEntriesTool exposes supported_subentry_types and short subentry IDs."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    class ReconfigurableSubentryFlow(ConfigSubentryFlow):
        """Subentry flow supporting reconfigure."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_show_form(step_id="user")

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_show_form(step_id="reconfigure")

    class StaticSubentryFlow(ConfigSubentryFlow):
        """Subentry flow without reconfigure."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_show_form(step_id="user")

    class FlowWithSubentries(ConfigFlow):
        """Config flow with subentry support."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {
                "agent": ReconfigurableSubentryFlow,
                "task": StaticSubentryFlow,
            }

    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="AI Hub",
        entry_id="01J00000000000000000008001",
        state=ConfigEntryState.LOADED,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_id="01J000000000000000000A8K2M",
                subentry_type="agent",
                title="Agent One",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={},
                subentry_id="01J000000000000000000B8K2M",
                subentry_type="agent",
                title="Agent Two",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={},
                subentry_id="01J00000000000000000009001",
                subentry_type="task",
                title="Task Runner",
                unique_id=None,
            ),
        ],
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Disabled Hub",
        entry_id="01J00000000000000000008002",
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    with mock_config_flow(TEST_DOMAIN, FlowWithSubentries):
        res = await llm_api.async_call_tool(
            llm.ToolInput("config__get_config_entries", {"domain": TEST_DOMAIN})
        )
        ambiguous = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8001",
                    "subentry_id": "agent:8K2M",
                },
            )
        )

    assert ambiguous == llm.ToolResult(
        data={"error": "Subentry 'agent:8K2M' not found."}, error=True
    )

    assert res == llm.ToolResult(
        data={
            "result": [
                {
                    "entry_id": f"{TEST_DOMAIN}:8001",
                    "domain": TEST_DOMAIN,
                    "title": "AI Hub",
                    "state": "loaded",
                    "supported_subentry_types": {
                        "agent": {"supports_reconfigure": True},
                        "task": {"supports_reconfigure": False},
                    },
                    "subentries": [
                        {
                            "subentry_id": "agent:A8K2M",
                            "subentry_type": "agent",
                            "title": "Agent One",
                        },
                        {
                            "subentry_id": "agent:B8K2M",
                            "subentry_type": "agent",
                            "title": "Agent Two",
                        },
                        {
                            "subentry_id": "task:9001",
                            "subentry_type": "task",
                            "title": "Task Runner",
                        },
                    ],
                },
                {
                    "entry_id": f"{TEST_DOMAIN}:8002",
                    "domain": TEST_DOMAIN,
                    "title": "Disabled Hub",
                    "state": "not_loaded",
                    "disabled_by": "user",
                },
            ]
        }
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.parametrize(
    "mock_translations",
    [
        {
            "config_subentries": {
                f"component.{TEST_DOMAIN}.config_subentries.agent.step.user.title": "Add agent",
                f"component.{TEST_DOMAIN}.config_subentries.agent.step.user.data.name": "Agent name",
                f"component.{TEST_DOMAIN}.config_subentries.agent.error.invalid_name": "Invalid agent name",
                f"component.{TEST_DOMAIN}.config_subentries.agent.create_entry.default": "Agent created",
            }
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains", "mock_translations")
async def test_subentry_create_flow(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test creating a subentry via start_flow and configure_flow."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="AI Hub",
        entry_id="01J00000000000000000008101",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    class AgentSubentryFlow(ConfigSubentryFlow):
        """Subentry flow for adding an agent."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            errors: dict[str, str] = {}
            if user_input is not None:
                if user_input["name"] == "bad":
                    errors["name"] = "invalid_name"
                else:
                    return self.async_create_entry(
                        title=user_input["name"],
                        data={"name": user_input["name"]},
                    )
            return self.async_show_form(
                step_id="user",
                data_schema=probatio.Schema({probatio.Required("name"): str}),
                errors=errors,
            )

    class FlowWithSubentry(ConfigFlow):
        """Config flow with agent subentry."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"agent": AgentSubentryFlow}

    with mock_config_flow(TEST_DOMAIN, FlowWithSubentry):
        started = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8101",
                    "subentry_type": "agent",
                },
            )
        )
        assert started.error is False
        assert isinstance(step := started.data["result"], dict)
        flow_id = step["flow_id"]
        assert step["title"] == "Add agent"
        assert step["fields"] == [
            {
                "name": "name",
                "required": True,
                "type": "string",
                "label": "Agent name",
            }
        ]

        inspected = await llm_api.async_call_tool(
            llm.ToolInput("config__configure_flow", {"flow_id": flow_id})
        )
        assert inspected == started

        err_res = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": flow_id, "user_input": {"name": "bad"}},
            )
        )
        assert err_res.error is False
        assert isinstance(err_step := err_res.data["result"], dict)
        assert err_step["errors"] == {"name": "Invalid agent name"}

        created = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": flow_id, "user_input": {"name": "Home Assistant"}},
            )
        )

    assert created == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id,
                "type": "create_entry",
                "title": "Home Assistant",
                "description": "Agent created",
            }
        }
    )
    subentries = list(entry.subentries.values())
    assert len(subentries) == 1
    assert subentries[0].subentry_type == "agent"
    assert subentries[0].title == "Home Assistant"
    assert subentries[0].data == {"name": "Home Assistant"}


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.parametrize(
    "mock_translations",
    [
        {
            "config_subentries": {
                f"component.{TEST_DOMAIN}.config_subentries.agent.step.reconfigure.title": "Reconfigure agent",
                f"component.{TEST_DOMAIN}.config_subentries.agent.step.reconfigure.data.model": "Model",
            }
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains", "mock_translations")
@pytest.mark.parametrize(
    "start_args",
    [
        pytest.param(
            {
                "flow_type": "subentry",
                "entry_id": f"{TEST_DOMAIN}:8201",
                "subentry_id": "agent:9201",
            },
            id="via_subentry_flow_type",
        ),
        pytest.param(
            {
                "flow_type": "reconfigure",
                "entry_id": f"{TEST_DOMAIN}:8201",
                "subentry_type": "agent",
                "subentry_id": "agent:9201",
            },
            id="via_reconfigure_flow_type",
        ),
    ],
)
async def test_subentry_reconfigure_flow(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    start_args: dict[str, Any],
) -> None:
    """Test reconfiguring an existing subentry and aborting a subentry flow."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="AI Hub",
        entry_id="01J00000000000000000008201",
        state=ConfigEntryState.LOADED,
        subentries_data=[
            ConfigSubentryData(
                data={"model": "v1"},
                subentry_id="01J00000000000000000009201",
                subentry_type="agent",
                title="Main Agent",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)

    class ReconfAgentSubentryFlow(ConfigSubentryFlow):
        """Subentry flow supporting reconfigure."""

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            subentry = self._get_reconfigure_subentry()
            if user_input is not None:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    data_updates={"model": user_input["model"]},
                )
            schema = self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required("model"): str}),
                subentry.data,
            )
            return self.async_show_form(step_id="reconfigure", data_schema=schema)

    class FlowWithSubentry(ConfigFlow):
        """Config flow with reconfigurable agent subentry."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"agent": ReconfAgentSubentryFlow}

    with mock_config_flow(TEST_DOMAIN, FlowWithSubentry):
        started = await llm_api.async_call_tool(
            llm.ToolInput("config__start_flow", start_args)
        )
        assert started.error is False
        assert isinstance(step := started.data["result"], dict)
        flow_id = step["flow_id"]
        assert step["title"] == "Reconfigure agent"
        assert step["fields"] == [
            {
                "name": "model",
                "required": True,
                "type": "string",
                "suggested_value": "v1",
                "label": "Model",
            }
        ]

        done = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": flow_id, "user_input": {"model": "v2"}},
            )
        )

        # Also verify aborting an in-progress subentry flow
        started_abort = await llm_api.async_call_tool(
            llm.ToolInput("config__start_flow", start_args)
        )
        assert isinstance(abort_step := started_abort.data["result"], dict)
        aborted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": abort_step["flow_id"], "abort": True},
            )
        )

    assert done == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id,
                "type": "abort",
                "reason": "reconfigure_successful",
                "description": "Reconfiguration was successful",
            }
        }
    )
    assert entry.subentries["01J00000000000000000009201"].data == {"model": "v2"}
    assert aborted == llm.ToolResult(
        data={
            "result": {
                "flow_id": abort_step["flow_id"],
                "type": "abort",
                "reason": "aborted",
            }
        }
    )
    assert hass.config_entries.subentries.async_progress() == []


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.parametrize(
    "mock_translations",
    [
        {
            "config_subentries": {
                f"component.{TEST_DOMAIN}.config_subentries.agent.abort.entry_not_loaded": "Parent entry must be loaded",
            }
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("ignore_translations_for_mock_domains", "mock_translations")
async def test_subentry_custom_abort_and_deleted_mid_flow(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test custom subentry abort translation and subentry deletion mid-flow."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="AI Hub",
        entry_id="01J00000000000000000008301",
        state=ConfigEntryState.LOADED,
        subentries_data=[
            ConfigSubentryData(
                data={"model": "v1"},
                subentry_id="01J00000000000000000009301",
                subentry_type="agent",
                title="Main Agent",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)

    class SubentryEdgeFlow(ConfigSubentryFlow):
        """Subentry flow that aborts on create and reconfigures an existing subentry."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_abort(reason="entry_not_loaded")

        async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            subentry = self._get_reconfigure_subentry()
            if user_input is not None:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, data_updates=user_input
                )
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=probatio.Schema({probatio.Required("model"): str}),
            )

    class FlowWithSubentry(ConfigFlow):
        """Config flow with agent subentry."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"agent": SubentryEdgeFlow}

    with mock_config_flow(TEST_DOMAIN, FlowWithSubentry):
        aborted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8301",
                    "subentry_type": "agent",
                },
            )
        )
        assert aborted.error is False
        assert isinstance(abort_res := aborted.data["result"], dict)
        assert abort_res["type"] == "abort"
        assert abort_res["reason"] == "entry_not_loaded"
        assert abort_res["description"] == "Parent entry must be loaded"

        started = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8301",
                    "subentry_id": "agent:9301",
                },
            )
        )
        assert isinstance(step := started.data["result"], dict)

        # Delete the subentry before submitting the reconfigure form
        hass.config_entries.async_remove_subentry(entry, "01J00000000000000000009301")

        deleted_res = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": step["flow_id"], "user_input": {"model": "v2"}},
            )
        )

    assert deleted_res == llm.ToolResult(
        data={"error": "Config entry or subentry no longer exists."}, error=True
    )
    assert hass.config_entries.subentries.async_progress() == []


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [TEST_DOMAIN])
@pytest.mark.usefixtures("ignore_translations_for_mock_domains")
async def test_subentry_parent_entry_removed_mid_flow(
    hass: HomeAssistant, llm_api: llm.APIInstance
) -> None:
    """Test subentry flows stay abortable and fail cleanly when the parent entry is removed."""
    mock_integration(hass, MockModule(TEST_DOMAIN))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)

    progress_started = asyncio.Event()
    progress_cancelled = asyncio.Event()

    async def _slow_task() -> None:
        progress_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            progress_cancelled.set()
            raise

    class ProgressSubentryFlow(ConfigSubentryFlow):
        """Subentry flow with a background progress task."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            task = hass.async_create_task(_slow_task())
            return self.async_show_progress(
                step_id="user", progress_action="working", progress_task=task
            )

    class FormSubentryFlow(ConfigSubentryFlow):
        """Subentry flow showing a simple form."""

        async def async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> SubentryFlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=probatio.Schema({probatio.Required("name"): str}),
            )

    class FlowWithSubentries(ConfigFlow):
        """Config flow with progress and form subentries."""

        @classmethod
        @callback
        @override
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[ConfigSubentryFlow]]:
            return {"progress": ProgressSubentryFlow, "form": FormSubentryFlow}

    entry1 = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Hub 1",
        entry_id="01J00000000000000000008401",
    )
    entry1.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=TEST_DOMAIN,
        title="Hub 2",
        entry_id="01J00000000000000000008402",
    )
    entry2.add_to_hass(hass)

    with mock_config_flow(TEST_DOMAIN, FlowWithSubentries):
        # 1. Start progress subentry flow, remove parent entry, then abort
        started_progress = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8401",
                    "subentry_type": "progress",
                },
            )
        )
        assert isinstance(progress_step := started_progress.data["result"], dict)
        await progress_started.wait()

        await hass.config_entries.async_remove(entry1.entry_id)

        aborted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": progress_step["flow_id"], "abort": True},
            )
        )
        await progress_cancelled.wait()

        # 2. Start form subentry flow, remove parent entry, then try to submit
        started_form = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__start_flow",
                {
                    "flow_type": "subentry",
                    "entry_id": f"{TEST_DOMAIN}:8402",
                    "subentry_type": "form",
                },
            )
        )
        assert isinstance(form_step := started_form.data["result"], dict)

        await hass.config_entries.async_remove(entry2.entry_id)

        submitted = await llm_api.async_call_tool(
            llm.ToolInput(
                "config__configure_flow",
                {"flow_id": form_step["flow_id"], "user_input": {"name": "test"}},
            )
        )

    assert aborted == llm.ToolResult(
        data={
            "result": {
                "flow_id": progress_step["flow_id"],
                "type": "abort",
                "reason": "aborted",
            }
        }
    )
    assert submitted == llm.ToolResult(
        data={"error": "Config entry or subentry no longer exists."}, error=True
    )
    assert hass.config_entries.subentries.async_progress() == []
