"""LLM tools for the repairs integration."""

from collections.abc import Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant import data_entry_flow
from homeassistant.components.llm import LLMTools, flow as llm_flow
from homeassistant.config_entries import UnknownEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    translation,
)
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
    substitute_translation_placeholders,
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DATA_REPAIRS, DOMAIN
from .issue_handler import RepairsFlowManager
from .models import RepairsFlowResult

_NON_EMPTY_STRING = probatio.All(str, probatio.Strip, probatio.NonEmpty())
_SEVERITY_ORDER = {severity.value: idx for idx, severity in enumerate(ir.IssueSeverity)}


def _resolve_language(hass: HomeAssistant, language: str | None) -> str:
    """Resolve a translation language code from an LLMContext language."""
    return language if language and language != "*" else hass.config.language


def _error_result(error: str) -> ToolResult:
    """Return an error ToolResult."""
    return ToolResult(data={"error": error}, error=True)


def _format_issue(issue: ir.IssueEntry, translations: dict[str, str]) -> JsonObjectType:
    """Format an active IssueEntry for LLM consumption."""
    if TYPE_CHECKING:
        assert issue.is_fixable is not None
        assert issue.severity is not None
        assert issue.translation_key is not None

    result: JsonObjectType = {
        "domain": issue.domain,
        "issue_id": issue.issue_id,
        "severity": str(issue.severity),
        "is_fixable": issue.is_fixable,
        "created": issue.created.isoformat(),
    }
    if issue.issue_domain and issue.issue_domain != issue.domain:
        result["issue_domain"] = issue.issue_domain
    key_prefix = f"component.{issue.domain}.issues.{issue.translation_key}"
    placeholders = issue.translation_placeholders or {}
    for field in ("title", "description"):
        if value := substitute_translation_placeholders(
            translations.get(f"{key_prefix}.{field}"), placeholders
        ):
            result[field] = value
    if issue.breaks_in_ha_version:
        result["breaks_in_ha_version"] = issue.breaks_in_ha_version
    if issue.learn_more_url:
        result["learn_more_url"] = issue.learn_more_url
    if issue.dismissed_version is not None:
        result["ignored"] = True
    return result


def _get_issues(
    hass: HomeAssistant,
    domains: set[str] | None,
    severity: str | None,
    include_ignored: bool,
) -> list[ir.IssueEntry]:
    """Return active, visible issues matching the filters, sorted by priority."""
    issue_registry = ir.async_get(hass)
    issues = [
        issue
        for issue in issue_registry.issues.values()
        if issue.active
        and not issue_registry.async_is_hidden(issue)
        and (include_ignored or issue.dismissed_version is None)
        and (domains is None or issue.domain.lower() in domains)
        and (severity is None or issue.severity == severity)
    ]
    issues.sort(
        key=lambda issue: (
            issue.dismissed_version is not None,
            _SEVERITY_ORDER.get(issue.severity or "", len(_SEVERITY_ORDER)),
            issue.domain,
            issue.issue_id,
        )
    )
    return issues


class GetIssuesTool(Tool):
    """LLM Tool to list and filter repair issues."""

    name = "repairs__get_issues"
    title = "Get repair issues"
    description = (
        "Retrieve active Home Assistant repair issues raised by integrations or core "
        "(such as broken automations, deprecated configurations, or device problems), "
        "including their severity, fixability, and translated title and description. "
        "Ignored issues are included by default and marked with 'ignored: true'; "
        "issues for disabled config entries are excluded."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "domain",
                description=(
                    "Filter by the issue's owning integration domain (e.g. "
                    "'automation', 'hue', 'mqtt', or 'homeassistant' for core "
                    "reauth and YAML issues)."
                ),
            ): probatio.All(
                probatio.EnsureList(),
                [_NON_EMPTY_STRING],
                probatio.Length(min=1),
            ),
            probatio.Optional(
                "severity",
                description="Filter by issue severity.",
            ): probatio.All(
                str,
                probatio.Lower,
                probatio.In([severity.value for severity in ir.IssueSeverity]),
            ),
            probatio.Optional(
                "include_ignored",
                description="Whether to include ignored (dismissed) issues in the results.",
                default=True,
            ): cv.boolean,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return matching repair issues."""
        args = self.parameters(tool_input.tool_args)
        issues = _get_issues(
            hass,
            domains={d.lower() for d in args["domain"]} if "domain" in args else None,
            severity=args.get("severity"),
            include_ignored=args["include_ignored"],
        )
        if not issues:
            return ToolResult(data={"issues": []})

        language = _resolve_language(hass, llm_context.language)
        translations = await translation.async_get_translations(
            hass,
            language,
            "issues",
            {issue.domain for issue in issues},
        )
        return ToolResult(
            data={
                "issues": list[JsonValueType](
                    _format_issue(issue, translations) for issue in issues
                )
            }
        )


async def _async_finalize_fix_flow_step(
    hass: HomeAssistant,
    flow_mgr: RepairsFlowManager,
    result: RepairsFlowResult,
    domain: str,
    issue_id: str,
    language: str | None,
    *,
    issue_translation_key: str | None,
    issue_placeholders: Mapping[str, str] | None,
) -> ToolResult:
    """Handle external steps or format a RepairsFlowResult with translations."""
    if result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP:
        with suppress(data_entry_flow.UnknownFlow):
            flow_mgr.async_abort(result["flow_id"])
        return ToolResult(
            data={
                "error": (
                    f"Repair fix flow for '{domain}/{issue_id}' requires browser "
                    "interaction (external step) and must be completed in the "
                    "Home Assistant UI at /config/repairs."
                ),
                "frontend_url": "/config/repairs",
            },
            error=True,
        )

    translations: dict[str, str] = {}
    base_prefix = ""
    fallback_title: str | None = None
    if issue_translation_key is not None:
        trans_domain: str = result.get("translation_domain") or domain
        translations = await translation.async_get_translations(
            hass,
            _resolve_language(hass, language),
            "issues",
            {domain, trans_domain},
        )
        base_prefix = (
            f"component.{trans_domain}.issues.{issue_translation_key}.fix_flow"
        )
        fallback_title = translations.get(
            f"component.{domain}.issues.{issue_translation_key}.title"
        )

    formatted = llm_flow.format_result(
        result,
        translations,
        base_prefix,
        fallback_title=fallback_title,
        extra_placeholders=issue_placeholders,
    )
    return ToolResult(data={"result": formatted})


class StartFixFlowTool(Tool):
    """LLM Tool to start a repair issue fix flow."""

    name = "repairs__start_fix_flow"
    title = "Start repair fix flow"
    description = (
        "Start a repair fix flow for a fixable Home Assistant repair issue and "
        "return its initial step. Use repairs__get_issues first to find the "
        "issue's 'domain' and 'issue_id' (only issues with 'is_fixable: true' "
        "have a fix flow)."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=False, open_world=True
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "domain",
                description=(
                    "The owning integration domain of the repair issue "
                    "(e.g. 'automation', 'homeassistant')."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Required(
                "issue_id",
                description="The issue_id of the fixable repair issue to fix.",
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Start a fix flow for the specified repair issue."""
        args = self.parameters(tool_input.tool_args)
        domain: str = args["domain"].lower()
        issue_id: str = args["issue_id"]

        issue_registry = ir.async_get(hass)
        issue = issue_registry.async_get_issue(domain, issue_id)
        if issue is None or not issue.active or issue_registry.async_is_hidden(issue):
            return _error_result(
                f"Repair issue '{issue_id}' for domain '{domain}' not found."
            )
        if not issue.is_fixable:
            return _error_result(
                f"Repair issue '{issue_id}' for domain '{domain}' is not fixable."
            )

        # Capture translation metadata before async_init, as immediate CREATE_ENTRY
        # deletes the issue from the registry.
        issue_translation_key = issue.translation_key
        issue_placeholders = issue.translation_placeholders

        flow_mgr = hass.data[DATA_REPAIRS].flow_manager
        try:
            result = await flow_mgr.async_init(domain, context={"issue_id": issue_id})
        except data_entry_flow.UnknownFlow, data_entry_flow.UnknownStep:
            return _error_result(
                f"Unable to start fix flow for repair issue '{issue_id}' "
                f"in domain '{domain}'."
            )
        except UnknownEntry as err:
            return _error_result(f"Config entry '{err}' not found in next_flow.")

        return await _async_finalize_fix_flow_step(
            hass,
            flow_mgr,
            result,
            domain,
            issue_id,
            llm_context.language,
            issue_translation_key=issue_translation_key,
            issue_placeholders=issue_placeholders,
        )


class ConfigureFixFlowTool(Tool):
    """LLM Tool to inspect, advance, or abort an in-progress repair fix flow."""

    name = "repairs__configure_fix_flow"
    title = "Configure repair fix flow step"
    description = (
        "Inspect, submit input to, or abort an in-progress repair fix flow by flow_id.\n"
        "- To inspect the current step without submitting, omit both 'user_input' and 'next_step_id'.\n"
        "- For a 'progress' step, omit both 'user_input' and 'next_step_id' to poll until it advances.\n"
        "- To submit a 'form' step, pass field values in 'user_input' (pass {} for "
        "a confirmation form with no fields).\n"
        "- To select an option in a 'menu' step, pass the option key in 'next_step_id'.\n"
        "- To cancel/abort the flow, set 'abort' to true."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=False, open_world=True
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "flow_id",
                description="The flow_id returned by repairs__start_fix_flow.",
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "user_input",
                description=(
                    "Field values to submit when the current step has type 'form' "
                    "(pass {} to confirm an empty form). Omit to fetch the current step state."
                ),
            ): dict,
            probatio.Optional(
                "next_step_id",
                description=(
                    "Menu option key to select when the current step has type 'menu'."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "abort",
                description="Set to true to cancel and abort the flow (default: false).",
                default=False,
            ): probatio.All(probatio.Boolean(), bool),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Configure or abort the specified repair fix flow."""
        args = self.parameters(tool_input.tool_args)
        flow_id: str = args["flow_id"]
        user_input: dict[str, Any] | None = args.get("user_input")
        next_step_id: str | None = args.get("next_step_id")
        abort: bool = args["abort"]

        # Capture flow and issue metadata before advancing, as CREATE_ENTRY pops
        # the flow and deletes the issue from the registry.
        flow_mgr = hass.data[DATA_REPAIRS].flow_manager
        domain = ""
        issue_id = ""
        issue_translation_key: str | None = None
        issue_placeholders: Mapping[str, str] | None = None
        if (flow_handler := flow_mgr._progress.get(flow_id)) is not None:  # noqa: SLF001
            domain = flow_handler.handler
            issue_id = flow_handler.context["issue_id"]
            if issue := ir.async_get(hass).async_get_issue(domain, issue_id):
                issue_translation_key = issue.translation_key
                issue_placeholders = issue.translation_placeholders

        try:
            step_result = await llm_flow.async_configure_step(
                flow_mgr,
                flow_id,
                user_input=user_input,
                next_step_id=next_step_id,
                abort=abort,
            )
        except UnknownEntry as err:
            return _error_result(f"Config entry '{err}' not found in next_flow.")
        if isinstance(step_result, ToolResult):
            return step_result

        return await _async_finalize_fix_flow_step(
            hass,
            flow_mgr,
            step_result,
            domain,
            issue_id,
            llm_context.language,
            issue_translation_key=issue_translation_key,
            issue_placeholders=issue_placeholders,
        )


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the repairs LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(
        tools=[
            GetIssuesTool(),
            StartFixFlowTool(),
            ConfigureFixFlowTool(),
        ]
    )
