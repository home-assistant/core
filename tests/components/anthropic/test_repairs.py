"""Tests for the Anthropic repairs flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.anthropic.const import CONF_CHAT_MODEL, DOMAIN
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


def _make_entry(
    hass: HomeAssistant,
    *,
    title: str,
    api_key: str,
    subentries_data: list[dict[str, Any]],
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
    entry.runtime_data = MagicMock()
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
    await async_process_repairs_platforms(hass)


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
                "data": {CONF_CHAT_MODEL: "claude-3-5-sonnet-20241022"},
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

    model_options: list[dict[str, str]] = [
        {"label": "Claude Haiku 4.5", "value": "claude-haiku-4-5"},
        {"label": "Claude Sonnet 4.5", "value": "claude-sonnet-4-5"},
        {"label": "Claude Opus 4.5", "value": "claude-opus-4-5"},
    ]

    with patch(
        "homeassistant.components.anthropic.repairs.get_model_list",
        new_callable=AsyncMock,
        return_value=model_options,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, "model_deprecated")
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        placeholders = result["description_placeholders"]
        assert placeholders["entry_name"] == entry_one.title
        assert placeholders["subentry_name"] == "Conversation One"
        assert placeholders["subentry_type"] == "Conversation agent"

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

        result = await process_repair_fix_flow(
            client,
            flow_id,
            json={CONF_CHAT_MODEL: "claude-sonnet-4-5"},
        )
        assert result["type"] == FlowResultType.FORM
        assert (
            _get_subentry(entry_one, "ai_task_data").data[CONF_CHAT_MODEL]
            == "claude-sonnet-4-5"
        )
        assert (
            _get_subentry(entry_one, "conversation").data[CONF_CHAT_MODEL]
            == "claude-haiku-4-5"
        )

        placeholders = result["description_placeholders"]
        assert placeholders["entry_name"] == entry_two.title
        assert placeholders["subentry_name"] == "Conversation Two"
        assert placeholders["subentry_type"] == "Conversation agent"

        result = await process_repair_fix_flow(
            client,
            flow_id,
            json={CONF_CHAT_MODEL: "claude-opus-4-5"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert (
            _get_subentry(entry_two, "conversation").data[CONF_CHAT_MODEL]
            == "claude-opus-4-5"
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
