"""Tests for the repairs LLM tools."""

import asyncio
import dataclasses
from typing import Any
from unittest.mock import Mock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser, mock_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant import data_entry_flow
from homeassistant.components.repairs import (
    DOMAIN,
    RepairsFlow,
    RepairsFlowResult,
    repairs_flow_manager,
)
from homeassistant.config_entries import ConfigEntryDisabler, UnknownEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import issue_registry as ir, llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

TOOL_NAME = "repairs__get_issues"
START_FIX_FLOW_TOOL = "repairs__start_fix_flow"
CONFIGURE_FIX_FLOW_TOOL = "repairs__configure_fix_flow"
ALL_TOOL_NAMES = [TOOL_NAME, START_FIX_FLOW_TOOL, CONFIGURE_FIX_FLOW_TOOL]
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
    """Test repairs tools are exposed only on the Home Assistant API."""
    assist_api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, llm_context)
    assert all(tool.name not in ALL_TOOL_NAMES for tool in assist_api.tools)

    repairs_tools = [tool for tool in llm_api.tools if tool.integration == DOMAIN]
    assert [tool.name for tool in repairs_tools] == ALL_TOOL_NAMES
    assert llm_api.api_prompt == ""
    assert {
        tool.name: {
            "title": tool.title,
            "description": tool.description,
            "annotations": tool.annotations,
            "parameters": probatio.to_openapi(
                tool.parameters,
                custom_serializer=llm_api.custom_serializer,
                openapi_version="3.1.0",
            ),
        }
        for tool in repairs_tools
    } == snapshot


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
    ("tool_name", "invalid_args"),
    [
        pytest.param(TOOL_NAME, {"domain": "   "}, id="get_issues_whitespace_domain"),
        pytest.param(TOOL_NAME, {"domain": []}, id="get_issues_empty_domain_list"),
        pytest.param(TOOL_NAME, {"severity": "info"}, id="get_issues_invalid_severity"),
        pytest.param(
            TOOL_NAME,
            {"include_ignored": "invalid"},
            id="get_issues_invalid_include_ignored",
        ),
        pytest.param(TOOL_NAME, {"unknown": True}, id="get_issues_unknown_arg"),
        pytest.param(
            START_FIX_FLOW_TOOL, {"domain": "automation"}, id="start_missing_issue_id"
        ),
        pytest.param(
            START_FIX_FLOW_TOOL, {"issue_id": "issue_1"}, id="start_missing_domain"
        ),
        pytest.param(
            START_FIX_FLOW_TOOL,
            {"domain": "   ", "issue_id": "issue_1"},
            id="start_whitespace_domain",
        ),
        pytest.param(
            START_FIX_FLOW_TOOL,
            {"domain": "automation", "issue_id": "   "},
            id="start_whitespace_issue_id",
        ),
        pytest.param(CONFIGURE_FIX_FLOW_TOOL, {}, id="configure_missing_flow_id"),
        pytest.param(
            CONFIGURE_FIX_FLOW_TOOL,
            {"flow_id": "   "},
            id="configure_whitespace_flow_id",
        ),
        pytest.param(
            CONFIGURE_FIX_FLOW_TOOL,
            {"flow_id": "flow_1", "user_input": "not_a_dict"},
            id="configure_invalid_user_input",
        ),
        pytest.param(
            CONFIGURE_FIX_FLOW_TOOL,
            {"flow_id": "flow_1", "next_step_id": "   "},
            id="configure_whitespace_next_step_id",
        ),
        pytest.param(
            CONFIGURE_FIX_FLOW_TOOL,
            {"flow_id": "flow_1", "abort": "not_a_bool"},
            id="configure_invalid_abort",
        ),
    ],
)
async def test_invalid_args(
    llm_api: llm.APIInstance,
    tool_name: str,
    invalid_args: JsonObjectType,
) -> None:
    """Test invalid arguments are rejected by the tool schemas."""
    with pytest.raises(probatio.Invalid):
        await llm_api.async_call_tool(llm.ToolInput(tool_name, invalid_args))


async def test_confirm_fix_flow_end_to_end(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_api: llm.APIInstance,
) -> None:
    """Test starting, inspecting, and confirming a default ConfirmRepairFlow."""
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

    start_res = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL,
            {"domain": "  AUTOMATION  ", "issue_id": "service_not_found_morning"},
        )
    )
    assert start_res.error is False
    step = start_res.data["result"]
    flow_id = step["flow_id"]
    assert step["type"] == "form"
    assert step["step_id"] == "confirm"
    assert step["title"] == "Morning uses an unknown action"
    assert "light.turn_on" in step["description"]
    assert step["fields"] == []

    inspect_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id})
    )
    assert inspect_res == start_res

    confirm_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id, "user_input": {}})
    )
    assert confirm_res == llm.ToolResult(
        data={"result": {"flow_id": flow_id, "type": "create_entry"}}
    )
    assert (
        issue_registry.async_get_issue("automation", "service_not_found_morning")
        is None
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.usefixtures("setup_issues")
@pytest.mark.parametrize(
    ("domain", "issue_id", "expected_error"),
    [
        pytest.param(
            "domain_a",
            "does_not_exist",
            "Repair issue 'does_not_exist' for domain 'domain_a' not found.",
            id="missing_issue",
        ),
        pytest.param(
            "domain_a",
            "inactive",
            "Repair issue 'inactive' for domain 'domain_a' not found.",
            id="inactive_issue",
        ),
        pytest.param(
            "domain_a",
            "hidden",
            "Repair issue 'hidden' for domain 'domain_a' not found.",
            id="hidden_issue",
        ),
        pytest.param(
            "domain_a",
            "warn_1",
            "Repair issue 'warn_1' for domain 'domain_a' is not fixable.",
            id="not_fixable",
        ),
    ],
)
async def test_start_fix_flow_validation_errors(
    llm_api: llm.APIInstance,
    domain: str,
    issue_id: str,
    expected_error: str,
) -> None:
    """Test start_fix_flow rejects missing, inactive, hidden, and unfixable issues."""
    result = await llm_api.async_call_tool(
        llm.ToolInput(START_FIX_FLOW_TOOL, {"domain": domain, "issue_id": issue_id})
    )
    assert result == llm.ToolResult(data={"error": expected_error}, error=True)


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        pytest.param(
            data_entry_flow.UnknownStep("step missing"),
            "Unable to start fix flow for repair issue 'broken_flow' in domain 'domain_a'.",
            id="unknown_step",
        ),
        pytest.param(
            data_entry_flow.UnknownFlow("flow missing"),
            "Unable to start fix flow for repair issue 'broken_flow' in domain 'domain_a'.",
            id="unknown_flow",
        ),
        pytest.param(
            UnknownEntry("missing_entry_123"),
            "Config entry 'missing_entry_123' not found in next_flow.",
            id="unknown_entry",
        ),
    ],
)
async def test_start_fix_flow_init_errors(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
    exc: Exception,
    expected_error: str,
) -> None:
    """Test start_fix_flow handles exceptions raised by flow_mgr.async_init."""
    ir.async_create_issue(
        hass,
        "domain_a",
        "broken_flow",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="broken_flow",
    )

    with patch.object(
        repairs_flow_manager(hass),
        "async_init",
        side_effect=exc,
    ):
        result = await llm_api.async_call_tool(
            llm.ToolInput(
                START_FIX_FLOW_TOOL,
                {"domain": "domain_a", "issue_id": "broken_flow"},
            )
        )

    assert result == llm.ToolResult(data={"error": expected_error}, error=True)


class _MenuAndFormFixFlow(RepairsFlow):
    """Test fix flow with a menu step followed by a validated form step."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show initial menu step."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["configure", "cancel"],
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show form step with validation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input["target"] == "bad":
                errors["target"] = "invalid_target"
            else:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="configure",
            data_schema=probatio.Schema({probatio.Required("target"): str}),
            errors=errors,
        )

    async def async_step_cancel(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Abort the fix flow."""
        return self.async_abort(
            reason="cancelled_by_user",
            translation_domain="domain_b",
        )


def _register_repairs_flow(
    hass: HomeAssistant, domain: str, flow_cls: type[RepairsFlow]
) -> None:
    """Register a mock repairs platform returning instances of flow_cls."""
    hass.config.components.add(domain)

    async def async_create_fix_flow(
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        return flow_cls()

    mock_platform(
        hass,
        f"{domain}.repairs",
        Mock(async_create_fix_flow=async_create_fix_flow),
    )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
@pytest.mark.parametrize(
    ("step_type", "submit_args"),
    [
        (data_entry_flow.FlowResultType.FORM, {"user_input": {}}),
        (data_entry_flow.FlowResultType.MENU, {"next_step_id": "finish"}),
    ],
)
async def test_inspect_fix_flow_preserves_pending_step(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_api: llm.APIInstance,
    step_type: data_entry_flow.FlowResultType,
    submit_args: JsonObjectType,
) -> None:
    """Inspect a stateful repair without advancing it or clearing its issue."""

    class StatefulFixFlow(RepairsFlow):
        async def async_step_init(
            self, user_input: dict[str, Any] | None = None
        ) -> RepairsFlowResult:
            if self.cur_step is not None:
                return self.async_create_entry(data={})
            if step_type is data_entry_flow.FlowResultType.FORM:
                return self.async_show_form(
                    step_id="init", data_schema=probatio.Schema({})
                )
            return self.async_show_menu(step_id="init", menu_options=["finish"])

        async def async_step_finish(
            self, user_input: dict[str, Any] | None = None
        ) -> RepairsFlowResult:
            return self.async_create_entry(data={})

    _register_repairs_flow(hass, "domain_a", StatefulFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "stateful_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="stateful_key",
    )
    start_res = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL, {"domain": "domain_a", "issue_id": "stateful_issue"}
        )
    )
    flow_id = start_res.data["result"]["flow_id"]

    inspect_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id})
    )
    assert inspect_res == start_res
    assert issue_registry.async_get_issue("domain_a", "stateful_issue") is not None

    done_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id, **submit_args})
    )
    assert done_res.data["result"]["type"] == "create_entry"
    assert issue_registry.async_get_issue("domain_a", "stateful_issue") is None


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_custom_fix_flow_menu_form_and_create_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_context: llm.LLMContext,
    llm_api: llm.APIInstance,
) -> None:
    """Test a multi-step custom fix flow with menu, validation errors, and translations."""
    llm_context.language = "de"
    _register_repairs_flow(hass, "domain_a", _MenuAndFormFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "custom_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="custom_key",
        translation_placeholders={"name": "Kitchen"},
    )

    mock_translations = {
        "component.domain_a.issues.custom_key.title": "Fix {name}",
        "component.domain_a.issues.custom_key.fix_flow.step.init.menu_options.configure": "Configure {name}",
        "component.domain_a.issues.custom_key.fix_flow.step.init.menu_options.cancel": "Cancel",
        "component.domain_a.issues.custom_key.fix_flow.step.configure.data.target": "Target device",
        "component.domain_a.issues.custom_key.fix_flow.error.invalid_target": "Invalid target for {name}",
        "component.domain_a.issues.custom_key.fix_flow.create_entry.default": "Updated {name}",
    }

    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ) as mock_get_translations:
        start_res = await llm_api.async_call_tool(
            llm.ToolInput(
                START_FIX_FLOW_TOOL,
                {"domain": "domain_a", "issue_id": "custom_issue"},
            )
        )
        assert start_res.error is False
        flow_id = start_res.data["result"]["flow_id"]
        assert start_res.data["result"] == {
            "flow_id": flow_id,
            "type": "menu",
            "step_id": "init",
            "title": "Fix Kitchen",
            "menu_options": {"configure": "Configure Kitchen", "cancel": "Cancel"},
        }
        mock_get_translations.assert_awaited_with(hass, "de", "issues", {"domain_a"})

        both_inputs_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {
                    "flow_id": flow_id,
                    "user_input": {},
                    "next_step_id": "configure",
                },
            )
        )
        assert both_inputs_res.error is True

        menu_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {"flow_id": flow_id, "next_step_id": "configure"},
            )
        )
        assert menu_res.error is False
        assert menu_res.data["result"]["type"] == "form"
        assert menu_res.data["result"]["step_id"] == "configure"
        assert menu_res.data["result"]["title"] == "Fix Kitchen"
        assert menu_res.data["result"]["fields"] == [
            {
                "name": "target",
                "required": True,
                "type": "string",
                "label": "Target device",
            }
        ]

        invalid_schema_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {"flow_id": flow_id, "user_input": {}},
            )
        )
        assert invalid_schema_res.error is True
        assert "Invalid input" in invalid_schema_res.data["error"]

        err_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {"flow_id": flow_id, "user_input": {"target": "bad"}},
            )
        )
        assert err_res.error is False
        assert err_res.data["result"]["errors"] == {
            "target": "Invalid target for Kitchen"
        }

        done_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {"flow_id": flow_id, "user_input": {"target": "good"}},
            )
        )
        assert done_res == llm.ToolResult(
            data={
                "result": {
                    "flow_id": flow_id,
                    "type": "create_entry",
                    "description": "Updated Kitchen",
                }
            }
        )

    assert issue_registry.async_get_issue("domain_a", "custom_issue") is None


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_custom_fix_flow_abort_and_cancel(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_api: llm.APIInstance,
) -> None:
    """Test flow-initiated abort (with translation_domain), user abort, and ignored issues."""
    _register_repairs_flow(hass, "domain_a", _MenuAndFormFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "abort_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="abort_key",
    )
    ir.async_ignore_issue(hass, "domain_a", "abort_issue", True)

    mock_translations = {
        "component.domain_b.issues.abort_key.fix_flow.abort.cancelled_by_user": "Cancelled",
    }
    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ) as mock_get_translations:
        start_res = await llm_api.async_call_tool(
            llm.ToolInput(
                START_FIX_FLOW_TOOL,
                {"domain": "domain_a", "issue_id": "abort_issue"},
            )
        )
        flow_id = start_res.data["result"]["flow_id"]
        abort_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL,
                {"flow_id": flow_id, "next_step_id": "cancel"},
            )
        )
        assert abort_res == llm.ToolResult(
            data={
                "result": {
                    "flow_id": flow_id,
                    "type": "abort",
                    "reason": "cancelled_by_user",
                    "description": "Cancelled",
                }
            }
        )
        mock_get_translations.assert_awaited_with(
            hass, "en", "issues", {"domain_a", "domain_b"}
        )

    assert issue_registry.async_get_issue("domain_a", "abort_issue") is not None

    start_res2 = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL,
            {"domain": "domain_a", "issue_id": "abort_issue"},
        )
    )
    flow_id2 = start_res2.data["result"]["flow_id"]
    user_abort_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id2, "abort": True})
    )
    assert user_abort_res == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id2,
                "type": "abort",
                "reason": "aborted",
            }
        }
    )
    assert issue_registry.async_get_issue("domain_a", "abort_issue") is not None


class _ImmediateCompleteFixFlow(RepairsFlow):
    """Test fix flow that completes immediately on init."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Complete immediately."""
        return self.async_create_entry(data={})


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_fix_flow_immediate_create_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_api: llm.APIInstance,
) -> None:
    """Test metadata is captured before async_init when flow completes immediately."""
    _register_repairs_flow(hass, "domain_a", _ImmediateCompleteFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "instant_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="instant_key",
        translation_placeholders={"item": "Sensor"},
    )

    mock_translations = {
        "component.domain_a.issues.instant_key.fix_flow.create_entry.default": "Fixed {item}",
    }
    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ):
        res = await llm_api.async_call_tool(
            llm.ToolInput(
                START_FIX_FLOW_TOOL,
                {"domain": "domain_a", "issue_id": "instant_issue"},
            )
        )

    assert res.error is False
    assert res.data["result"]["type"] == "create_entry"
    assert res.data["result"]["description"] == "Fixed Sensor"
    assert issue_registry.async_get_issue("domain_a", "instant_issue") is None


class _ExternalStepFixFlow(RepairsFlow):
    """Test fix flow that returns an external step on init."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Return an external step."""
        return self.async_external_step(
            step_id="init", url="https://example.com/repair"
        )


class _DelayedExternalStepFixFlow(RepairsFlow):
    """Test fix flow that returns an external step after a form step."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Forward to the confirmation step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show a form step before transitioning to an external step."""
        if user_input is not None:
            return await self.async_step_auth()
        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}))

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Return an external step."""
        return self.async_external_step(
            step_id="auth", url="https://example.com/repair"
        )


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_fix_flow_external_step_rejected_on_start(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
) -> None:
    """Test external steps returned by start_fix_flow are aborted with a UI redirect."""
    _register_repairs_flow(hass, "domain_a", _ExternalStepFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "ext_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="ext_key",
    )

    res = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL, {"domain": "domain_a", "issue_id": "ext_issue"}
        )
    )
    assert res == llm.ToolResult(
        data={
            "error": (
                "Repair fix flow for 'domain_a/ext_issue' requires browser "
                "interaction (external step) and must be completed in the "
                "Home Assistant UI at /config/repairs."
            ),
            "frontend_url": "/config/repairs",
        },
        error=True,
    )
    assert repairs_flow_manager(hass).async_progress() == []


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_fix_flow_external_step_rejected_on_configure(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
) -> None:
    """Test external steps returned by configure_fix_flow are aborted with a UI redirect."""
    _register_repairs_flow(hass, "domain_a", _DelayedExternalStepFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "ext_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="ext_key",
    )

    start_res = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL, {"domain": "domain_a", "issue_id": "ext_issue"}
        )
    )
    assert start_res.error is False
    res = await llm_api.async_call_tool(
        llm.ToolInput(
            CONFIGURE_FIX_FLOW_TOOL,
            {"flow_id": start_res.data["result"]["flow_id"], "user_input": {}},
        )
    )
    assert res == llm.ToolResult(
        data={
            "error": (
                "Repair fix flow for 'domain_a/ext_issue' requires browser "
                "interaction (external step) and must be completed in the "
                "Home Assistant UI at /config/repairs."
            ),
            "frontend_url": "/config/repairs",
        },
        error=True,
    )
    assert repairs_flow_manager(hass).async_progress() == []


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_fix_flow_progress_step(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    llm_api: llm.APIInstance,
) -> None:
    """Test polling a SHOW_PROGRESS repair fix flow until it completes."""
    gate = asyncio.Event()

    class _ProgressFixFlow(RepairsFlow):
        progress_task: asyncio.Task[None] | None = None

        async def _do_work(self) -> None:
            await gate.wait()

        async def async_step_init(
            self, user_input: dict[str, Any] | None = None
        ) -> RepairsFlowResult:
            if not self.progress_task:
                self.progress_task = self.hass.async_create_task(self._do_work())
            if not self.progress_task.done():
                return self.async_show_progress(
                    step_id="init",
                    progress_action="repairing",
                    progress_task=self.progress_task,
                )
            return self.async_show_progress_done(next_step_id="finish")

        async def async_step_finish(
            self, user_input: dict[str, Any] | None = None
        ) -> RepairsFlowResult:
            return self.async_create_entry(data={})

    _register_repairs_flow(hass, "domain_a", _ProgressFixFlow)
    ir.async_create_issue(
        hass,
        "domain_a",
        "progress_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="progress_key",
    )

    mock_translations = {
        "component.domain_a.issues.progress_key.fix_flow.progress.repairing": "Repairing...",
        "component.domain_a.issues.progress_key.fix_flow.create_entry.default": "Repair complete",
    }
    with patch(
        "homeassistant.components.repairs.llm.translation.async_get_translations",
        return_value=mock_translations,
    ):
        start_res = await llm_api.async_call_tool(
            llm.ToolInput(
                START_FIX_FLOW_TOOL,
                {"domain": "domain_a", "issue_id": "progress_issue"},
            )
        )
        flow_id = start_res.data["result"]["flow_id"]
        assert start_res.data["result"] == {
            "flow_id": flow_id,
            "type": "progress",
            "step_id": "init",
            "progress_action": "repairing",
            "description": "Repairing...",
        }

        poll_res = await llm_api.async_call_tool(
            llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id})
        )
        assert poll_res == start_res

        gate.set()
        await hass.async_block_till_done()

        done_res = await llm_api.async_call_tool(
            llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id})
        )
        assert done_res == llm.ToolResult(
            data={
                "result": {
                    "flow_id": flow_id,
                    "type": "create_entry",
                    "description": "Repair complete",
                }
            }
        )

    assert issue_registry.async_get_issue("domain_a", "progress_issue") is None


@pytest.mark.parametrize("ignore_translations_for_mock_domains", [MOCK_DOMAINS])
async def test_configure_fix_flow_errors_and_deleted_issue(
    hass: HomeAssistant,
    llm_api: llm.APIInstance,
) -> None:
    """Test configure_fix_flow error handling and externally deleted issues."""
    missing_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": "unknown-flow"})
    )
    assert missing_res == llm.ToolResult(
        data={"error": "Flow 'unknown-flow' not found."}, error=True
    )

    ir.async_create_issue(
        hass,
        "domain_a",
        "vanishing_issue",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="vanishing_key",
    )
    start_res = await llm_api.async_call_tool(
        llm.ToolInput(
            START_FIX_FLOW_TOOL,
            {"domain": "domain_a", "issue_id": "vanishing_issue"},
        )
    )
    flow_id = start_res.data["result"]["flow_id"]

    with patch.object(
        repairs_flow_manager(hass),
        "async_configure",
        side_effect=UnknownEntry("missing_entry_456"),
    ):
        unknown_entry_res = await llm_api.async_call_tool(
            llm.ToolInput(
                CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id, "user_input": {}}
            )
        )
    assert unknown_entry_res == llm.ToolResult(
        data={"error": "Config entry 'missing_entry_456' not found in next_flow."},
        error=True,
    )

    ir.async_delete_issue(hass, "domain_a", "vanishing_issue")

    inspect_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id})
    )
    assert inspect_res == llm.ToolResult(
        data={
            "result": {
                "flow_id": flow_id,
                "type": "form",
                "step_id": "confirm",
                "fields": [],
            }
        }
    )

    done_res = await llm_api.async_call_tool(
        llm.ToolInput(CONFIGURE_FIX_FLOW_TOOL, {"flow_id": flow_id, "user_input": {}})
    )
    assert done_res == llm.ToolResult(
        data={"result": {"flow_id": flow_id, "type": "create_entry"}}
    )
