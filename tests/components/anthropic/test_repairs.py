"""Tests for the Anthropic repairs flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from anthropic import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    NotFoundError,
)
from anthropic.pagination import AsyncPage
from anthropic.types import ModelInfo
from httpx import Request, Response
import pytest

from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_THINKING_EFFORT,
    DOMAIN,
)
from homeassistant.components.anthropic.coordinator import model_alias
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

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


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
            models=MagicMock(list=AsyncMock(return_value=AsyncPage(data=model_list)))
        )
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

    ir.async_create_issue(
        hass,
        DOMAIN,
        "model_deprecated",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_deprecated",
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
    assert placeholders["retirement_date"] == "February 19th, 2026"

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
    assert placeholders["retirement_date"] == "February 19th, 2026"

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
    assert placeholders["retirement_date"] == "January 5th, 2026"

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
                "data": {CONF_CHAT_MODEL: "claude-sonnet-4-5"},
                "subentry_type": "conversation",
                "title": "Conversation One",
                "unique_id": None,
            }
        ],
    )

    ir.async_create_issue(
        hass,
        DOMAIN,
        "model_deprecated",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_deprecated",
    )

    await _setup_repairs(hass)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None


@pytest.mark.parametrize(
    "available_models",
    [
        pytest.param(model_list, id="listed_model"),
        pytest.param([], id="custom_model"),
    ],
)
@pytest.mark.parametrize(
    ("model", "thinking_effort", "expected_effort"),
    [
        pytest.param("claude-opus-5-5", "none", "low", id="opus_5_5"),
        pytest.param("claude-fable-5", "none", "low", id="fable_5"),
        pytest.param("claude-fable-5-1", "none", "low", id="fable_5_1"),
        pytest.param(
            "claude-opus-5-5-20260921", "none", "low", id="versioned_opus_5_5"
        ),
        pytest.param("claude-opus-5-5", "high", "high", id="adaptive_effort"),
        pytest.param("claude-opus-4-6", "none", "none", id="optional_thinking"),
        pytest.param(
            "claude-opus-4-6-20260204", "none", "none", id="versioned_optional_thinking"
        ),
        pytest.param("claude-opus-4-5", "none", "none", id="nonadaptive_effort"),
        pytest.param("claude-haiku-4-5", "none", "none", id="no_effort_support"),
    ],
)
async def test_repair_flow_thinking_effort(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    available_models: list[ModelInfo],
    model: str,
    thinking_effort: str,
    expected_effort: str,
) -> None:
    """Repair incompatible disabled thinking while preserving valid effort settings."""
    entry = _make_entry(
        hass,
        title="Claude",
        api_key="key",
        subentries_data=[
            {
                "data": {
                    CONF_CHAT_MODEL: "claude-3-7-sonnet-20250219",
                    CONF_THINKING_EFFORT: thinking_effort,
                    CONF_MAX_TOKENS: 4096,
                },
                "subentry_type": "conversation",
                "title": "Conversation",
                "unique_id": None,
            }
        ],
    )
    entry.runtime_data.client.models.list.return_value = AsyncPage(
        data=available_models
    )
    entry.runtime_data.client.models.retrieve = AsyncMock(
        return_value=next(
            model_info
            for model_info in model_list
            if model_alias(model_info.id) == model_alias(model)
        )
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "model_deprecated",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_deprecated",
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
    assert _get_subentry(entry, "conversation").data == {
        CONF_CHAT_MODEL: model,
        CONF_THINKING_EFFORT: expected_effort,
        CONF_MAX_TOKENS: 4096,
    }


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
    entry.runtime_data.client.models.list.return_value = AsyncPage(data=[])
    retrieve = entry.runtime_data.client.models.retrieve = AsyncMock(
        side_effect=[
            error,
            next(model for model in model_list if model.id == "claude-opus-5-5"),
        ]
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "model_deprecated",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_deprecated",
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
        "retirement_date": "February 19th, 2026",
    }
    assert _get_subentry(entry, "conversation").data == {
        **conversation_data,
        CONF_CHAT_MODEL: "claude-opus-5-5",
        CONF_THINKING_EFFORT: "low",
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
