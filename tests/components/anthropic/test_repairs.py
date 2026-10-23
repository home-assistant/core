"""Tests for the Anthropic repairs flow."""

import datetime as dt
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from anthropic import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    NotFoundError,
)
from anthropic.pagination import AsyncPage
from anthropic.types import ModelInfo, ModelLine
from httpx2 import Request, Response
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_CODE_EXECUTION,
    CONF_MAX_TOKENS,
    CONF_THINKING_BUDGET,
    CONF_THINKING_EFFORT,
    CONF_TOOL_SEARCH,
    CONF_WEB_FETCH,
    CONF_WEB_FETCH_MAX_USES,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DOMAIN,
)
from homeassistant.components.anthropic.coordinator import (
    AnthropicCoordinator,
    model_alias,
)
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import model_list

WEB_SEARCH_OPTIONS = {
    CONF_WEB_SEARCH: True,
    CONF_WEB_SEARCH_MAX_USES: 3,
    CONF_WEB_SEARCH_USER_LOCATION: True,
    CONF_WEB_SEARCH_CITY: "San Francisco",
    CONF_WEB_SEARCH_REGION: "California",
    CONF_WEB_SEARCH_COUNTRY: "US",
    CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
}
SERVER_TOOL_OPTIONS = {CONF_CODE_EXECUTION: True, **WEB_SEARCH_OPTIONS}


def _deprecated_model(
    model_id: str, line: ModelLine, retires_at: dt.datetime
) -> ModelInfo:
    """Return synthetic metadata for an obsolete model."""
    return ModelInfo(
        id=model_id,
        type="model",
        display_name=model_id,
        created_at=dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        deprecated_at=dt.datetime(2025, 8, 13, tzinfo=dt.UTC),
        retires_at=retires_at,
        lifecycle="deprecated",
        line=line,
    )


DEPRECATED_MODEL_LIST = [
    _deprecated_model(
        "claude-3-5-haiku-20241022",
        "haiku",
        dt.datetime(2026, 2, 19, tzinfo=dt.UTC),
    ),
    _deprecated_model(
        "claude-3-7-sonnet-20250219",
        "sonnet",
        dt.datetime(2026, 2, 19, tzinfo=dt.UTC),
    ),
    _deprecated_model(
        "claude-3-opus-20240229",
        "opus",
        dt.datetime(2026, 1, 5, tzinfo=dt.UTC),
    ),
]


def _copy_model_info(model_id: str) -> ModelInfo:
    """Return an independent copy of the live model metadata."""
    return next(
        model for model in model_list if model_alias(model.id) == model_alias(model_id)
    ).model_copy(deep=True)


def _model_info_without_thinking() -> ModelInfo:
    """Return metadata for a model without thinking support."""
    model_info = _copy_model_info("claude-haiku-4-5")
    assert model_info.capabilities
    model_info.capabilities.thinking.supported = False
    model_info.capabilities.thinking.types.enabled.supported = False
    return model_info


def _model_info_with_server_tools(
    code_execution_supported: bool, web_search_supported: bool
) -> ModelInfo:
    """Return model metadata with independent server-tool capabilities."""
    model_info = _copy_model_info("claude-haiku-5-5")
    assert model_info.capabilities
    assert model_info.capabilities.code_execution.supported
    server_tools = model_info.capabilities.server_tools
    server_tools.code_execution.supported = code_execution_supported
    server_tools.web_search.supported = web_search_supported
    server_tools.supported = code_execution_supported or web_search_supported
    return model_info


def _make_entry(
    hass: HomeAssistant,
    *,
    title: str,
    api_key: str,
    subentries_data: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a config entry with subentries and runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={"api_key": api_key},
        version=2,
        subentries_data=subentries_data,
    )
    entry.add_to_hass(hass)
    object.__setattr__(entry, "state", ConfigEntryState.LOADED)
    entry.runtime_data = SimpleNamespace(
        client=MagicMock(
            models=MagicMock(
                list=AsyncMock(return_value=AsyncPage(data=model_list, has_more=False))
            )
        ),
        data=[*model_list, *DEPRECATED_MODEL_LIST],
    )
    entry.runtime_data.get_model_info = partial(
        AnthropicCoordinator.get_model_info, entry.runtime_data
    )
    return entry


def _get_subentry(
    entry: MockConfigEntry,
    subentry_type: str,
) -> ConfigSubentry:
    """Return the first subentry of a type."""
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == subentry_type
    )


async def _setup_repairs(hass: HomeAssistant) -> None:
    """Set up repairs and create an obsolete-model issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "model_deprecated",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_deprecated",
    )
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "repairs", {})


async def test_repair_flow_iterates_subentries(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow iterates across deprecated subentries."""
    entry_one: MockConfigEntry = _make_entry(
        hass,
        title="Entry One",
        api_key="key-one",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"},
                "subentry_type": "conversation",
                "title": "Conversation One",
                "unique_id": None,
            },
            {
                "data": {CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219"},
                "subentry_type": "ai_task_data",
                "title": "AI task One",
                "unique_id": None,
            },
        ],
    )
    entry_two: MockConfigEntry = _make_entry(
        hass,
        title="Entry Two",
        api_key="key-two",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-opus-20240229"},
                "subentry_type": "conversation",
                "title": "Conversation Two",
                "unique_id": None,
            },
        ],
    )

    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    placeholders = result["description_placeholders"]
    assert placeholders["entry_name"] == entry_one.title
    assert placeholders["subentry_name"] == "Conversation One"
    assert placeholders["subentry_type"] == "Conversation agent"
    assert placeholders["retirement_date"] == "2026-02-19"

    flow_id = result["flow_id"]

    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-haiku-4-5"},
    )
    assert result["type"] == FlowResultType.FORM
    assert (
        _get_subentry(entry_one, "conversation").data[CONF_CHAT_MODEL]
        == "claude-haiku-4-5"
    )

    placeholders = result["description_placeholders"]
    assert placeholders["entry_name"] == entry_one.title
    assert placeholders["subentry_name"] == "AI task One"
    assert placeholders["subentry_type"] == "AI task"
    assert placeholders["retirement_date"] == "2026-02-19"

    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-sonnet-4-6"},
    )
    assert result["type"] == FlowResultType.FORM
    assert (
        _get_subentry(entry_one, "ai_task_data").data[CONF_CHAT_MODEL]
        == "claude-sonnet-4-6"
    )
    assert (
        _get_subentry(entry_one, "conversation").data[CONF_CHAT_MODEL]
        == "claude-haiku-4-5"
    )

    placeholders = result["description_placeholders"]
    assert placeholders["entry_name"] == entry_two.title
    assert placeholders["subentry_name"] == "Conversation Two"
    assert placeholders["subentry_type"] == "Conversation agent"
    assert placeholders["retirement_date"] == "2026-01-05"

    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-opus-4-6"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        _get_subentry(entry_two, "conversation").data[CONF_CHAT_MODEL]
        == "claude-opus-4-6"
    )

    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None


async def test_repair_flow_no_deprecated_models(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow completes when everything was fixed."""
    _make_entry(
        hass,
        title="Entry One",
        api_key="key-one",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-sonnet-4-6"},
                "subentry_type": "conversation",
                "title": "Conversation One",
                "unique_id": None,
            }
        ],
    )

    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None


@pytest.mark.parametrize(
    "cached_model_count",
    [
        pytest.param(1, id="listed_model"),
        pytest.param(0, id="custom_model"),
    ],
)
@pytest.mark.parametrize(
    "subentry_type",
    [
        pytest.param("conversation", id="conversation"),
        pytest.param("ai_task_data", id="ai_task"),
    ],
)
@pytest.mark.parametrize(
    ("model", "model_info", "model_options", "expected_options"),
    [
        pytest.param(
            "claude-opus-5-5",
            _copy_model_info("claude-opus-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="opus_5_5",
        ),
        pytest.param(
            "claude-fable-5",
            _copy_model_info("claude-fable-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="fable_5",
        ),
        pytest.param(
            "claude-fable-5-1",
            _copy_model_info("claude-fable-5-1"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="fable_5_1",
        ),
        pytest.param(
            "claude-opus-5-5-20260921",
            _copy_model_info("claude-opus-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="versioned_opus_5_5",
        ),
        pytest.param(
            "claude-sonnet-5-5",
            _copy_model_info("claude-sonnet-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="sonnet_5_5",
        ),
        pytest.param(
            "claude-sonnet-5-5-20260928",
            _copy_model_info("claude-sonnet-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="versioned_sonnet_5_5",
        ),
        pytest.param(
            "claude-haiku-5-5",
            _copy_model_info("claude-haiku-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {CONF_THINKING_EFFORT: "none"},
            id="haiku_5_5",
        ),
        pytest.param(
            "claude-haiku-5-5-20261007",
            _copy_model_info("claude-haiku-5-5"),
            {CONF_THINKING_EFFORT: "none"},
            {CONF_THINKING_EFFORT: "none"},
            id="versioned_haiku_5_5",
        ),
        pytest.param(
            "claude-opus-5-5",
            _copy_model_info("claude-opus-5-5"),
            {CONF_THINKING_EFFORT: "high"},
            {CONF_THINKING_EFFORT: "high"},
            id="adaptive_effort",
        ),
        pytest.param(
            "claude-opus-4-6",
            _copy_model_info("claude-opus-4-6"),
            {CONF_THINKING_EFFORT: "none"},
            {CONF_THINKING_EFFORT: "none"},
            id="optional_thinking",
        ),
        pytest.param(
            "claude-opus-4-6-20260204",
            _copy_model_info("claude-opus-4-6"),
            {CONF_THINKING_EFFORT: "none"},
            {CONF_THINKING_EFFORT: "none"},
            id="versioned_optional_thinking",
        ),
        pytest.param(
            "claude-opus-4-5",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="nonadaptive_effort",
        ),
        pytest.param(
            "claude-opus-4-5-20251101",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="versioned_nonadaptive_effort",
        ),
        pytest.param(
            "claude-opus-4-5",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_EFFORT: "high"},
            {CONF_THINKING_EFFORT: "high"},
            id="valid_nonadaptive_effort",
        ),
        pytest.param(
            "claude-haiku-4-5",
            _copy_model_info("claude-haiku-4-5"),
            {CONF_THINKING_EFFORT: "none"},
            {},
            id="no_effort_support",
        ),
        pytest.param(
            "claude-haiku-5-5",
            _copy_model_info("claude-haiku-5-5"),
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            {CONF_THINKING_EFFORT: "high"},
            id="adaptive_removes_manual_budget",
        ),
        pytest.param(
            "claude-opus-4-5",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            id="manual_thinking_budget_and_effort",
        ),
        pytest.param(
            "claude-haiku-4-5",
            _copy_model_info("claude-haiku-4-5"),
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            {CONF_THINKING_BUDGET: 4096},
            id="manual_thinking_without_effort",
        ),
        pytest.param(
            "claude-haiku-4-5",
            _model_info_without_thinking(),
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            {},
            id="unsupported_thinking",
        ),
        pytest.param(
            "claude-haiku-5-5",
            _copy_model_info("claude-haiku-5-5").model_copy(
                update={"capabilities": None}, deep=True
            ),
            {CONF_THINKING_BUDGET: 4096, CONF_THINKING_EFFORT: "high"},
            {},
            id="unknown_capabilities",
        ),
        pytest.param(
            "claude-opus-4-5",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_EFFORT: "max"},
            {},
            id="unsupported_max_effort",
        ),
        pytest.param(
            "claude-opus-4-5",
            _copy_model_info("claude-opus-4-5"),
            {CONF_THINKING_EFFORT: "xhigh"},
            {},
            id="unsupported_xhigh_effort",
        ),
        pytest.param(
            "claude-opus-5-5",
            _copy_model_info("claude-opus-5-5"),
            {CONF_TOOL_SEARCH: True},
            {CONF_TOOL_SEARCH: True},
            id="supported_tool_search",
        ),
        pytest.param(
            "claude-haiku-5-5",
            _copy_model_info("claude-haiku-5-5"),
            {CONF_TOOL_SEARCH: True},
            {},
            id="unsupported_tool_search",
        ),
        pytest.param(
            "claude-opus-5-5",
            _copy_model_info("claude-opus-5-5"),
            {},
            {},
            id="unrelated_options",
        ),
    ],
)
async def test_repair_flow_model_options(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    cached_model_count: int,
    subentry_type: str,
    model: str,
    model_info: ModelInfo,
    model_options: dict[str, int | str | bool],
    expected_options: dict[str, int | str | bool],
) -> None:
    """Reconcile stored model options against the selected model's capabilities."""
    preserved_options = {
        CONF_MAX_TOKENS: 8192,
        CONF_CODE_EXECUTION: True,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_MAX_USES: 3,
        CONF_WEB_SEARCH_USER_LOCATION: True,
        CONF_WEB_SEARCH_CITY: "San Francisco",
        CONF_WEB_SEARCH_REGION: "California",
        CONF_WEB_SEARCH_COUNTRY: "US",
        CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        CONF_WEB_FETCH: True,
        CONF_WEB_FETCH_MAX_USES: 7,
    }
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {
                    CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219",
                    **preserved_options,
                    **model_options,
                },
                "subentry_type": subentry_type,
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[model_info][:cached_model_count], has_more=False
    )
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        return_value=model_info
    )
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
    result = await process_repair_fix_flow(
        client,
        result["flow_id"],
        json={CONF_CHAT_MODEL: model},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, subentry_type).data == {
        CONF_CHAT_MODEL: model,
        **preserved_options,
        **expected_options,
    }
    assert (
        retrieve.await_args_list
        == [call(model, timeout=10.0)][: 1 - cached_model_count]
    )


@pytest.mark.parametrize(
    "cached_model_count",
    [
        pytest.param(1, id="listed_model"),
        pytest.param(0, id="custom_model"),
    ],
)
@pytest.mark.parametrize(
    ("model_info", "server_tool_options", "expected_options"),
    [
        pytest.param(
            _model_info_with_server_tools(False, True),
            SERVER_TOOL_OPTIONS,
            {CONF_THINKING_EFFORT: "high", **WEB_SEARCH_OPTIONS},
            id="unsupported_code_execution",
        ),
        pytest.param(
            _model_info_with_server_tools(True, False),
            SERVER_TOOL_OPTIONS,
            {CONF_THINKING_EFFORT: "high", CONF_CODE_EXECUTION: True},
            id="unsupported_web_search",
        ),
        pytest.param(
            _model_info_with_server_tools(False, False),
            SERVER_TOOL_OPTIONS,
            {CONF_THINKING_EFFORT: "high"},
            id="unsupported_server_tools",
        ),
        pytest.param(
            _model_info_with_server_tools(True, True),
            SERVER_TOOL_OPTIONS,
            {CONF_THINKING_EFFORT: "high", **SERVER_TOOL_OPTIONS},
            id="supported_server_tools",
        ),
        pytest.param(
            _model_info_with_server_tools(False, False).model_copy(
                update={"capabilities": None}, deep=True
            ),
            SERVER_TOOL_OPTIONS,
            SERVER_TOOL_OPTIONS,
            id="unknown_capabilities",
        ),
        pytest.param(
            _model_info_with_server_tools(False, False),
            {CONF_CODE_EXECUTION: False, CONF_WEB_SEARCH: False},
            {CONF_THINKING_EFFORT: "high"},
            id="disabled_unsupported_server_tools",
        ),
    ],
)
async def test_repair_flow_server_tool_options(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    cached_model_count: int,
    model_info: ModelInfo,
    server_tool_options: dict[str, bool | int | str],
    expected_options: dict[str, bool | int | str],
) -> None:
    """Clear unsupported server-tool options while preserving unrelated settings."""
    preserved_options = {
        CONF_MAX_TOKENS: 8192,
        CONF_WEB_FETCH: True,
        CONF_WEB_FETCH_MAX_USES: 7,
    }
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {
                    CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219",
                    CONF_THINKING_EFFORT: "high",
                    CONF_TOOL_SEARCH: True,
                    **preserved_options,
                    **server_tool_options,
                },
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[model_info][:cached_model_count], has_more=False
    )
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        return_value=model_info
    )
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
    result = await process_repair_fix_flow(
        client,
        result["flow_id"],
        json={CONF_CHAT_MODEL: "claude-haiku-5-5-20261007"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-haiku-5-5-20261007",
        **preserved_options,
        **expected_options,
    }
    assert (
        retrieve.await_args_list
        == [call("claude-haiku-5-5-20261007", timeout=10.0)][: 1 - cached_model_count]
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            APITimeoutError(request=Request("GET", "https://api.anthropic.com")),
            id="timeout",
        ),
        pytest.param(
            APIConnectionError(request=Request("GET", "https://api.anthropic.com")),
            id="connection_error",
        ),
        pytest.param(
            NotFoundError(
                "Model not found",
                response=Response(
                    404, request=Request("GET", "https://api.anthropic.com")
                ),
                body=None,
            ),
            id="not_found",
        ),
        pytest.param(
            InternalServerError(
                "Server unavailable",
                response=Response(
                    500, request=Request("GET", "https://api.anthropic.com")
                ),
                body=None,
            ),
            id="server_error",
        ),
    ],
)
async def test_repair_flow_model_lookup_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    error: APIError,
) -> None:
    """Keep the current repair available for retry when model lookup fails."""
    conversation_data = {
        CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219",
        CONF_THINKING_EFFORT: "none",
        CONF_MAX_TOKENS: 4096,
    }
    task_data = {CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"}
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": conversation_data,
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            },
            {
                "data": task_data,
                "subentry_type": "ai_task_data",
                "title": "AI task",
                "unique_id": None,
            },
        ],
    )
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[], has_more=False
    )
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        side_effect=[
            error,
            next(model for model in model_list if model.id == "claude-opus-5-5"),
            _copy_model_info("claude-haiku-4-5"),
        ]
    )
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
    flow_id = result["flow_id"]
    placeholders = result["description_placeholders"]
    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-opus-5-5"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["flow_id"] == flow_id
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_CHAT_MODEL: "api_error"}
    assert result["description_placeholders"] == {
        **placeholders,
        "message": error.message,
    }
    model_field = next(
        field for field in result["data_schema"] if field["name"] == CONF_CHAT_MODEL
    )
    assert model_field["description"]["suggested_value"] == "claude-opus-5-5"
    assert _get_subentry(entry, "conversation").data == conversation_data
    assert _get_subentry(entry, "ai_task_data").data == task_data
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    retrieve.assert_awaited_once_with("claude-opus-5-5", timeout=10.0)

    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-opus-5-5"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["flow_id"] == flow_id
    assert not result["errors"]
    assert result["description_placeholders"] == {
        "entry_name": entry.title,
        "model": "claude-3-5-haiku-20241022",
        "subentry_name": "AI task",
        "subentry_type": "AI task",
        "retirement_date": "2026-02-19",
        "deprecation_date": "2025-08-13",
    }
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-opus-5-5",
        CONF_MAX_TOKENS: 4096,
    }
    assert _get_subentry(entry, "ai_task_data").data == task_data
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    assert retrieve.await_count == 2
    entry.runtime_data.client.models.list.assert_awaited_once_with(timeout=10.0)

    result = await process_repair_fix_flow(
        client,
        flow_id,
        json={CONF_CHAT_MODEL: "claude-haiku-4-5"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, "ai_task_data").data == {
        CONF_CHAT_MODEL: "claude-haiku-4-5"
    }
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None
    assert retrieve.await_count == 3
    retrieve.assert_awaited_with("claude-haiku-4-5", timeout=10.0)


@pytest.mark.parametrize(
    ("model_info", "expected_step", "deprecation_date", "retirement_date"),
    [
        pytest.param(
            DEPRECATED_MODEL_LIST[0].model_copy(update={"id": "custom-obsolete"}),
            "init",
            "2025-08-13",
            "2026-02-19",
            id="deprecated_with_past_retirement_date",
        ),
        pytest.param(
            DEPRECATED_MODEL_LIST[0].model_copy(
                update={"id": "custom-obsolete", "lifecycle": "retired"}
            ),
            "retired",
            "2025-08-13",
            "2026-02-19",
            id="retired",
        ),
        pytest.param(
            DEPRECATED_MODEL_LIST[0].model_copy(
                update={
                    "id": "custom-obsolete",
                    "deprecated_at": None,
                    "retires_at": None,
                }
            ),
            "init",
            "—",
            "—",
            id="missing_dates",
        ),
    ],
)
async def test_repair_flow_lifecycle_metadata(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    model_info: ModelInfo,
    expected_step: str,
    deprecation_date: str,
    retirement_date: str,
) -> None:
    """Use API lifecycle and dates for custom models."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "custom-obsolete"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.data = [model_info]
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == expected_step
    assert result["description_placeholders"] == {
        "entry_name": entry.title,
        "model": "custom-obsolete",
        "subentry_name": "Conversation",
        "subentry_type": "Conversation agent",
        "deprecation_date": deprecation_date,
        "retirement_date": retirement_date,
    }

    result = await process_repair_fix_flow(
        client,
        result["flow_id"],
        json={CONF_CHAT_MODEL: "claude-haiku-5-5"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-haiku-5-5"
    }


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(
            [
                DEPRECATED_MODEL_LIST[0].model_copy(
                    update={"id": "claude-active-haiku", "lifecycle": "active"}
                )
            ],
            id="active_model",
        ),
        pytest.param([], id="unknown_model_retired_fallback"),
    ],
)
async def test_repair_flow_skips_active_and_unknown_models(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    metadata: list[ModelInfo],
) -> None:
    """Only authoritative API deprecation or retirement metadata starts a repair."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-active-haiku"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.data = metadata
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry.runtime_data.client.models.list.assert_not_awaited()
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-active-haiku"
    }


@pytest.mark.parametrize(
    ("line", "expected_model"),
    [
        pytest.param("haiku", "claude-opus-1", id="metadata_line"),
        pytest.param(None, None, id="no_line"),
        pytest.param("mythos", None, id="no_active_model_in_line"),
    ],
)
async def test_repair_flow_model_selection(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    line: ModelLine | None,
    expected_model: str | None,
) -> None:
    """Use matching model lines in API order and offer only active models."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.data = [
        DEPRECATED_MODEL_LIST[1].model_copy(update={"line": line})
    ]
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[
            DEPRECATED_MODEL_LIST[0],
            DEPRECATED_MODEL_LIST[0].model_copy(
                update={"id": "retired-haiku", "lifecycle": "retired"}
            ),
            _copy_model_info("claude-sonnet-5-5").model_copy(
                update={"id": "claude-haiku-99"}
            ),
            _copy_model_info("claude-haiku-5-5").model_copy(
                update={"id": "claude-opus-1"}
            ),
            _copy_model_info("claude-haiku-5-5").model_copy(
                update={"id": "claude-opus-99"}
            ),
        ],
        has_more=False,
    )
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.FORM
    model_field = next(
        field for field in result["data_schema"] if field["name"] == CONF_CHAT_MODEL
    )
    assert model_field.get("default") == expected_model
    assert model_field["selector"]["select"]["options"] == [
        {"label": "Claude Sonnet 5.5", "value": "claude-haiku-99"},
        {"label": "Claude Haiku 5.5", "value": "claude-opus-1"},
        {"label": "Claude Haiku 5.5", "value": "claude-opus-99"},
    ]


@pytest.mark.freeze_time("2026-10-16T12:00:00Z")
@pytest.mark.parametrize(
    ("sdk_key", "retirement_date", "submitted_model"),
    [
        pytest.param(
            "claude-sonnet-4-5-20250929",
            "November 30th, 2026",
            "claude-sonnet-4-5",
            id="deprecated_version",
        ),
        pytest.param(
            "claude-sonnet-4-5",
            "November 30th, 2026",
            "claude-sonnet-4-5",
            id="deprecated_alias",
        ),
        pytest.param(
            "claude-sonnet-4-5",
            "November 30th, 2026",
            "claude-sonnet-4-5-20250929",
            id="deprecated_alias_dated_submission",
        ),
        pytest.param(
            "claude-sonnet-4-5-20250929",
            "October 15th, 2026",
            "claude-sonnet-4-5-20250929",
            id="retired_version",
        ),
        pytest.param(
            "claude-sonnet-4-5-20250929",
            "unknown",
            "claude-sonnet-4-5",
            id="unknown_retirement_date",
        ),
    ],
)
async def test_repair_flow_sdk_inactive_current_model(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    sdk_key: str,
    retirement_date: str,
    submitted_model: str,
) -> None:
    """Do not offer or accept the current model when only the SDK marks it inactive."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-sonnet-4-5"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    current_model = _copy_model_info("claude-sonnet-4-5")
    active_model = _copy_model_info("claude-sonnet-5-5")
    entry.runtime_data.data = [current_model, active_model]
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[current_model, active_model], has_more=False
    )
    await _setup_repairs(hass)
    client = await hass_client()

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {sdk_key: retirement_date},
        clear=True,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

        assert result["type"] == FlowResultType.FORM
        model_field = next(
            field for field in result["data_schema"] if field["name"] == CONF_CHAT_MODEL
        )
        assert model_field["default"] == "claude-sonnet-5-5"
        assert model_field["selector"]["select"]["options"] == [
            {"label": "Claude Sonnet 5.5", "value": "claude-sonnet-5-5"}
        ]
        flow_id = result["flow_id"]
        step_id = result["step_id"]
        placeholders = result["description_placeholders"]

        result = await process_repair_fix_flow(
            client, flow_id, json={CONF_CHAT_MODEL: submitted_model}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["flow_id"] == flow_id
        assert result["step_id"] == step_id
        assert result["errors"] == {CONF_CHAT_MODEL: "model_not_active"}
        assert result["description_placeholders"] == placeholders
        assert _get_subentry(entry, "conversation").data == {
            CONF_CHAT_MODEL: "claude-sonnet-4-5"
        }
        assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
        assert current_model.lifecycle == "active"
        entry.runtime_data.client.models.retrieve.assert_not_called()

        result = await process_repair_fix_flow(
            client, flow_id, json={CONF_CHAT_MODEL: "claude-sonnet-5-5"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-sonnet-5-5"
    }
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None


async def test_repair_flow_model_list_pagination(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Find replacement models beyond the first API response page."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=[_copy_model_info("claude-sonnet-5-5")], has_more=True
    )
    second_page = AsyncPage(data=[_copy_model_info("claude-haiku-5-5")], has_more=False)
    await _setup_repairs(hass)
    client = await hass_client()

    with (
        patch.object(AsyncPage, "has_next_page", side_effect=[True, False]),
        patch.object(AsyncPage, "get_next_page", return_value=second_page) as next_page,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.FORM
    model_field = next(
        field for field in result["data_schema"] if field["name"] == CONF_CHAT_MODEL
    )
    assert model_field["default"] == "claude-haiku-5-5"
    next_page.assert_awaited_once()

    result = await process_repair_fix_flow(
        client,
        result["flow_id"],
        json={CONF_CHAT_MODEL: "claude-haiku-5-5"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry.runtime_data.client.models.list.assert_awaited_once_with(timeout=10.0)
    entry.runtime_data.client.models.retrieve.assert_not_called()


@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("deprecated", id="deprecated_replacement"),
        pytest.param("retired", id="retired_replacement"),
    ],
)
@pytest.mark.parametrize(
    "current_lifecycle",
    [
        pytest.param("deprecated", id="deprecated_target"),
        pytest.param("retired", id="retired_target"),
    ],
)
async def test_repair_flow_inactive_custom_model(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    lifecycle: str,
    current_lifecycle: str,
) -> None:
    """Keep the current repair available when a custom replacement is inactive."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.data = [
        DEPRECATED_MODEL_LIST[0].model_copy(update={"lifecycle": current_lifecycle})
    ]
    inactive_model = _copy_model_info("claude-haiku-5-5").model_copy(
        update={"id": "custom-model", "lifecycle": lifecycle}
    )
    active_model = inactive_model.model_copy(update={"lifecycle": "active"})
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        side_effect=[inactive_model, active_model]
    )
    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
    flow_id = result["flow_id"]
    step_id = result["step_id"]
    placeholders = result["description_placeholders"]
    result = await process_repair_fix_flow(
        client, flow_id, json={CONF_CHAT_MODEL: "custom-model"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["flow_id"] == flow_id
    assert result["step_id"] == step_id
    assert result["errors"] == {CONF_CHAT_MODEL: "model_not_active"}
    assert result["description_placeholders"] == placeholders
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"
    }
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    retrieve.assert_awaited_once_with("custom-model", timeout=10.0)

    result = await process_repair_fix_flow(
        client, flow_id, json={CONF_CHAT_MODEL: "custom-model"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "custom-model"
    }
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None
    assert retrieve.await_args_list == [call("custom-model", timeout=10.0)] * 2


@pytest.mark.freeze_time("2026-10-16T12:00:00Z")
@pytest.mark.parametrize(
    ("sdk_key", "submitted_model", "retirement_date"),
    [
        pytest.param(
            "custom-model",
            "custom-model",
            "November 30th, 2026",
            id="deprecated_alias",
        ),
        pytest.param(
            "custom-model-20260101",
            "custom-model-20260101",
            "October 15th, 2026",
            id="retired_version",
        ),
        pytest.param(
            "custom-model",
            "custom-model-20260101",
            "November 30th, 2026",
            id="deprecated_alias_dated_submission",
        ),
    ],
)
async def test_repair_flow_sdk_inactive_custom_model(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    sdk_key: str,
    submitted_model: str,
    retirement_date: str,
) -> None:
    """Reject directly retrieved active API models deprecated or retired in the SDK."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"},
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    custom_model = _copy_model_info("claude-haiku-5-5").model_copy(
        update={"id": "custom-model-20260101"}
    )
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        return_value=custom_model
    )
    await _setup_repairs(hass)
    client = await hass_client()

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {sdk_key: retirement_date},
        clear=True,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
        flow_id = result["flow_id"]
        placeholders = result["description_placeholders"]
        result = await process_repair_fix_flow(
            client, flow_id, json={CONF_CHAT_MODEL: submitted_model}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["flow_id"] == flow_id
    assert result["errors"] == {CONF_CHAT_MODEL: "model_not_active"}
    assert result["description_placeholders"] == placeholders
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: "claude-3-5-haiku-20241022"
    }
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    assert custom_model.lifecycle == "active"
    retrieve.assert_awaited_once_with(submitted_model, timeout=10.0)
