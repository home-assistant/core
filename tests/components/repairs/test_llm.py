"""Tests for the repairs LLM tools."""

import dataclasses
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.repairs import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import issue_registry as ir, llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

TOOL_NAME = "repairs__get_issues"
MOCK_DOMAINS = ["domain_a", "domain_b"]


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="*",
        assistant="conversation",
        device_id=None,
    )


@pytest.fixture
async def llm_api(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    llm_context: llm.LLMContext,
) -> llm.APIInstance:
    """Set up repairs and llm components and return the Home Assistant LLM API."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)
    return await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)


@pytest.fixture
def setup_issues(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Populate representative issues covering sorting, visibility, and filters."""
    disabled_entry = MockConfigEntry(
        domain="domain_a", disabled_by=ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)

    for domain, issue_id, severity, issue_domain, entry_id in (
        ("domain_a", "warn_1", ir.IssueSeverity.WARNING, None, None),
        ("domain_b", "err_0", ir.IssueSeverity.ERROR, "other_domain", None),
        ("domain_a", "err_2", ir.IssueSeverity.ERROR, None, None),
        ("domain_a", "err_1", ir.IssueSeverity.ERROR, None, None),
        ("domain_b", "crit_1", ir.IssueSeverity.CRITICAL, None, None),
        (
            "domain_a",
            "hidden",
            ir.IssueSeverity.CRITICAL,
            None,
            disabled_entry.entry_id,
        ),
        ("domain_b", "ignored_warn", ir.IssueSeverity.WARNING, None, None),
        ("domain_a", "ignored_crit", ir.IssueSeverity.CRITICAL, None, None),
    ):
        ir.async_create_issue(
            hass,
            domain,
            issue_id,
            config_entry_id=entry_id,
            is_fixable=False,
            issue_domain=issue_domain,
            severity=severity,
            translation_key=issue_id,
        )

    ir.async_ignore_issue(hass, "domain_b", "ignored_warn", True)
    ir.async_ignore_issue(hass, "domain_a", "ignored_crit", True)
    issue_registry.issues[("domain_a", "inactive")] = dataclasses.replace(
        issue_registry.issues[("domain_b", "ignored_warn")],
        active=False,
        domain="domain_a",
        issue_id="inactive",
        severity=None,
    )


async def test_tool_exposure_and_schema(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    llm_api: llm.APIInstance,
    snapshot: SnapshotAssertion,
) -> None:
    """Test repairs__get_issues is exposed only on the Home Assistant API."""
    assist_api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, llm_context)
    assert all(tool.name != TOOL_NAME for tool in assist_api.tools)

    repairs_tools = [tool for tool in llm_api.tools if tool.integration == DOMAIN]
    assert [tool.name for tool in repairs_tools] == [TOOL_NAME]
    tool = repairs_tools[0]
    assert tool.title == "Get repair issues"
    assert tool.description
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    assert llm_api.api_prompt == ""
    assert (
        probatio.to_openapi(
            tool.parameters,
            custom_serializer=llm_api.custom_serializer,
            openapi_version="3.1.0",
        )
        == snapshot
    )


@pytest.mark.freeze_time("2026-11-16 02:00:00+00:00")
async def test_get_issues_formatting(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    snapshot: SnapshotAssertion,
) -> None:
    """Test full issue payload formatting through the Home Assistant API."""
    ir.async_create_issue(
        hass,
        "automation",
        "service_not_found_morning",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="service_not_found",
        translation_placeholders={
            "service": "light.turn_on",
            "entity_id": "automation.morning",
            "name": "Morning",
            "edit": "/config/automation/edit/1",
        },
    )
    ir.async_create_issue(
        hass,
        "homeassistant",
        "deprecated_yaml_aqualogic",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain="aqualogic",
        learn_more_url="https://www.home-assistant.io/integrations/aqualogic",
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": "aqualogic",
            "integration_title": "AquaLogic",
        },
    )
    ir.async_create_issue(
        hass,
        "homeassistant",
        "ignored_demo_yaml",
        is_fixable=False,
        issue_domain="homeassistant",
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": "demo",
            "integration_title": "Demo",
        },
    )
    ir.async_ignore_issue(hass, "homeassistant", "ignored_demo_yaml", True)

    result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))
    assert result == snapshot


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.usefixtures("setup_issues")
@pytest.mark.parametrize(
    ("tool_args", "expected_ids"),
    [
        pytest.param(
            {},
            [
                "crit_1",
                "err_1",
                "err_2",
                "err_0",
                "warn_1",
                "ignored_crit",
                "ignored_warn",
            ],
            id="default_priority_sort",
        ),
        pytest.param(
            {"include_ignored": False},
            ["crit_1", "err_1", "err_2", "err_0", "warn_1"],
            id="exclude_ignored",
        ),
        pytest.param(
            {"domain": "  DOMAIN_A  "},
            ["err_1", "err_2", "warn_1", "ignored_crit"],
            id="single_domain",
        ),
        pytest.param(
            {"domain": "other_domain"},
            [],
            id="does_not_match_issue_domain",
        ),
        pytest.param(
            {"domain": ["domain_b", " DOMAIN_A "], "severity": "ERROR"},
            ["err_1", "err_2", "err_0"],
            id="domain_list_and_severity",
        ),
        pytest.param(
            {"severity": "warning", "include_ignored": "false"},
            ["warn_1"],
            id="severity_without_ignored",
        ),
    ],
)
async def test_get_issues_filtering_and_sorting(
    llm_api: llm.APIInstance,
    tool_args: JsonObjectType,
    expected_ids: list[str],
) -> None:
    """Test priority sorting, visibility rules, and filtering."""
    result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, tool_args))
    assert [item["issue_id"] for item in result.data["issues"]] == expected_ids


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.parametrize(
    ("context_language", "expected_language"),
    [
        pytest.param("de", "de", id="explicit_context_language"),
        pytest.param("*", "nl", id="wildcard_uses_hass_language"),
        pytest.param(None, "nl", id="none_uses_hass_language"),
    ],
)
async def test_get_issues_language_resolution(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    llm_api: llm.APIInstance,
    context_language: str | None,
    expected_language: str,
) -> None:
    """Test translation language resolution from LLMContext and hass.config."""
    llm_context.language = context_language
    hass.config.language = "nl"
    ir.async_create_issue(
        hass,
        "domain_a",
        "issue_1",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="issue_1",
    )

    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value={},
    ) as mock_get_translations:
        await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))

    mock_get_translations.assert_awaited_once_with(
        hass, expected_language, "issues", {"domain_a"}
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.parametrize("replacement", ["value", "Notify {edit}"])
async def test_get_issues_missing_translations_and_placeholders(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    replacement: str,
) -> None:
    """Test omitted missing translations and partial placeholder substitution."""
    ir.async_create_issue(
        hass,
        "domain_a",
        "partial_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="partial_key",
        translation_placeholders={
            "known": replacement,
            "edit": "/config/automation/edit/1",
        },
    )
    ir.async_create_issue(
        hass,
        "domain_b",
        "orphan_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="orphan_key",
    )

    mock_translations = {
        "component.domain_a.issues.partial_key.title": "Found {known} {missing}",
        "component.domain_a.issues.partial_key.description": "Details for {known}",
    }
    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ):
        result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))

    assert [
        (item["issue_id"], item.get("title"), item.get("description"))
        for item in result.data["issues"]
    ] == [
        (
            "partial_issue",
            f"Found {replacement} {{missing}}",
            f"Details for {replacement}",
        ),
        ("orphan_issue", None, None),
    ]


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"domain": "   "}, id="whitespace_domain"),
        pytest.param({"domain": []}, id="empty_domain_list"),
        pytest.param({"severity": "info"}, id="invalid_severity"),
        pytest.param({"include_ignored": "invalid"}, id="invalid_include_ignored"),
        pytest.param({"unknown": True}, id="unknown_arg"),
    ],
)
async def test_get_issues_invalid_args(
    llm_api: llm.APIInstance,
    invalid_args: JsonObjectType,
) -> None:
    """Test invalid arguments are rejected by the schema."""
    with pytest.raises(probatio.Invalid):
        await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, invalid_args))
