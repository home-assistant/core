"""Tests for the repairs LLM tools."""

from typing import Any
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


async def test_get_issues_empty(llm_api: llm.APIInstance) -> None:
    """Test empty issue list when no active issues exist."""
    result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))
    assert result == llm.ToolResult(data={"issues": []})


@pytest.mark.parametrize("load_registries", [False])
async def test_get_issues_sorting_storage_and_hidden_entries(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_admin_user: MockUser,
    llm_context: llm.LLMContext,
) -> None:
    """Test sorting tie-breakers, storage-loaded issues, and hidden entries."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "breaks_in_ha_version": None,
                    "config_entry_id": None,
                    "config_subentry_id": None,
                    "created": "2026-11-16T01:00:00+00:00",
                    "data": None,
                    "dismissed_version": None,
                    "domain": "automation",
                    "is_fixable": True,
                    "is_persistent": True,
                    "issue_domain": None,
                    "issue_id": "z_persistent_error",
                    "learn_more_url": None,
                    "severity": "error",
                    "translation_key": "service_not_found",
                    "translation_placeholders": {
                        "service": "light.turn_on",
                        "entity_id": "automation.z",
                        "name": "Z",
                        "edit": "/config/automation/edit/z",
                    },
                },
                {
                    "config_entry_id": None,
                    "config_subentry_id": None,
                    "created": "2026-11-16T01:00:00+00:00",
                    "dismissed_version": "2026.11.0",
                    "domain": "homeassistant",
                    "is_persistent": False,
                    "issue_id": "inactive_dismissed",
                },
            ]
        },
    }
    await ir.async_load(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)
    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)

    enabled_entry = MockConfigEntry(domain="automation", title="Enabled")
    enabled_entry.add_to_hass(hass)
    disabled_entry = MockConfigEntry(
        domain="automation",
        title="Disabled",
        disabled_by=ConfigEntryDisabler.USER,
    )
    disabled_entry.add_to_hass(hass)

    # Insert sensor before homeassistant at same severity to test domain tie-breaker
    ir.async_create_issue(
        hass,
        "sensor",
        "units_changed_sensor.power",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="units_changed",
        translation_placeholders={"statistic_id": "sensor.power"},
    )
    ir.async_create_issue(
        hass,
        "homeassistant",
        "yaml_aqualogic",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": "aqualogic",
            "integration_title": "AquaLogic",
        },
    )
    # Same (ignored=False, severity=ERROR, domain="automation") as z_persistent_error
    ir.async_create_issue(
        hass,
        "automation",
        "a_runtime_error",
        config_entry_id=enabled_entry.entry_id,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="service_not_found",
        translation_placeholders={
            "service": "light.turn_on",
            "entity_id": "automation.a",
            "name": "A",
            "edit": "/config/automation/edit/a",
        },
    )
    ir.async_create_issue(
        hass,
        "automation",
        "validation_failed_critical",
        is_fixable=False,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key="validation_failed_actions",
        translation_placeholders={
            "entity_id": "automation.alarm",
            "name": "Alarm",
            "error": "Invalid config",
            "edit": "/config/automation/edit/2",
        },
    )
    ir.async_create_issue(
        hass,
        "automation",
        "hidden_disabled_entry",
        config_entry_id=disabled_entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="validation_failed_actions",
        translation_placeholders={
            "entity_id": "automation.disabled",
            "name": "Disabled",
            "error": "Disabled",
            "edit": "/config/automation/edit/3",
        },
    )
    # Insert ignored WARNING before ignored CRITICAL to test ignored severity sort
    ir.async_create_issue(
        hass,
        "sensor",
        "ignored_warn",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="units_changed",
        translation_placeholders={"statistic_id": "sensor.ignored"},
    )
    ir.async_ignore_issue(hass, "sensor", "ignored_warn", True)
    ir.async_create_issue(
        hass,
        "homeassistant",
        "ignored_critical",
        is_fixable=False,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": "demo",
            "integration_title": "Demo",
        },
    )
    ir.async_ignore_issue(hass, "homeassistant", "ignored_critical", True)

    default_result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))
    assert [item["issue_id"] for item in default_result.data["issues"]] == [
        "validation_failed_critical",
        "a_runtime_error",
        "z_persistent_error",
        "yaml_aqualogic",
        "units_changed_sensor.power",
        "ignored_critical",
        "ignored_warn",
    ]

    without_ignored = await api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"include_ignored": "false"})
    )
    assert [item["issue_id"] for item in without_ignored.data["issues"]] == [
        "validation_failed_critical",
        "a_runtime_error",
        "z_persistent_error",
        "yaml_aqualogic",
        "units_changed_sensor.power",
    ]


@pytest.mark.parametrize(
    ("tool_args", "expected_ids"),
    [
        pytest.param(
            {"domain": "  AUTOMATION  "},
            ["auto_error"],
            id="single_domain",
        ),
        pytest.param(
            {"domain": "aqualogic"},
            [],
            id="does_not_match_issue_domain",
        ),
        pytest.param(
            {"domain": ["sensor", "  HOMEASSISTANT "]},
            ["yaml_aqualogic", "sensor_warn"],
            id="domain_list",
        ),
        pytest.param(
            {"severity": "ERROR"},
            ["auto_error"],
            id="severity_error",
        ),
        pytest.param(
            {"domain": "homeassistant", "severity": "warning"},
            ["yaml_aqualogic"],
            id="domain_and_severity",
        ),
        pytest.param(
            {"domain": "hue"},
            [],
            id="no_matches",
        ),
    ],
)
async def test_get_issues_filtering(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    tool_args: JsonObjectType,
    expected_ids: list[str],
) -> None:
    """Test filtering repair issues by domain and severity."""
    ir.async_create_issue(
        hass,
        "automation",
        "auto_error",
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
        "yaml_aqualogic",
        is_fixable=False,
        issue_domain="aqualogic",
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": "aqualogic",
            "integration_title": "AquaLogic",
        },
    )
    ir.async_create_issue(
        hass,
        "sensor",
        "sensor_warn",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="units_changed",
        translation_placeholders={"statistic_id": "sensor.power"},
    )

    result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, tool_args))
    assert [item["issue_id"] for item in result.data["issues"]] == expected_ids


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
        "sensor",
        "sensor_warn",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="units_changed",
        translation_placeholders={"statistic_id": "sensor.power"},
    )

    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value={},
    ) as mock_get_translations:
        await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))

    mock_get_translations.assert_awaited_once_with(
        hass, expected_language, "issues", {"sensor"}
    )


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    [["uninstalled_custom_domain"]],
)
async def test_get_issues_uninstalled_domain_real_translations(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
) -> None:
    """Test real translation lookup when an issue belongs to an unknown domain."""
    ir.async_create_issue(
        hass,
        "uninstalled_custom_domain",
        "orphan_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="orphan_translation_key",
    )

    result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))
    assert [
        (item["issue_id"], "title" in item, "description" in item)
        for item in result.data["issues"]
    ] == [("orphan_issue", False, False)]


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    [["custom_partial", "custom_plain"]],
)
async def test_get_issues_placeholder_substitution(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
) -> None:
    """Test placeholder substitution with missing placeholders and plain strings."""
    ir.async_create_issue(
        hass,
        "custom_partial",
        "partial_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="partial_key",
        translation_placeholders={"known": "value", "empty": ""},
    )
    ir.async_create_issue(
        hass,
        "custom_plain",
        "plain_issue",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="plain_key",
    )

    mock_translations = {
        "component.custom_partial.issues.partial_key.title": (
            "Found {known} [{empty}] {missing}"
        ),
        "component.custom_partial.issues.partial_key.description": (
            "Details for {known} and {missing}"
        ),
        "component.custom_plain.issues.plain_key.title": "Plain title",
        "component.custom_plain.issues.plain_key.description": "Plain description",
    }

    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ):
        result = await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))

    assert [
        (item["issue_id"], item["title"], item["description"])
        for item in result.data["issues"]
    ] == [
        (
            "partial_issue",
            "Found value [] {missing}",
            "Details for value and {missing}",
        ),
        ("plain_issue", "Plain title", "Plain description"),
    ]


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"domain": ""}, id="empty_domain_str"),
        pytest.param({"domain": "   "}, id="whitespace_domain_str"),
        pytest.param({"domain": []}, id="empty_domain_list"),
        pytest.param({"domain": ["hue", "   "]}, id="valid_and_whitespace_domain"),
        pytest.param({"domain": 123}, id="non_str_domain"),
        pytest.param({"domain": None}, id="none_domain"),
        pytest.param({"severity": "info"}, id="invalid_severity"),
        pytest.param({"severity": None}, id="none_severity"),
        pytest.param({"include_ignored": "invalid"}, id="invalid_include_ignored"),
        pytest.param({"include_ignored": None}, id="none_include_ignored"),
        pytest.param({"include_ignored": []}, id="list_include_ignored"),
        pytest.param({"unknown": True}, id="unknown_arg"),
    ],
)
async def test_get_issues_invalid_args(
    llm_api: llm.APIInstance,
    invalid_args: JsonObjectType,
) -> None:
    """Test invalid arguments raise probatio.Invalid."""
    with pytest.raises(probatio.Invalid):
        await llm_api.async_call_tool(llm.ToolInput(TOOL_NAME, invalid_args))
