"""LLM tools for the repairs integration."""

from typing import TYPE_CHECKING, override

import probatio

from homeassistant.components.llm import LLMTools
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
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN

_NON_EMPTY_STRING = probatio.All(str, probatio.Strip, probatio.NonEmpty())
_SEVERITIES = [severity.value for severity in ir.IssueSeverity]
_SEVERITY_ORDER: dict[str, int] = {
    ir.IssueSeverity.CRITICAL: 0,
    ir.IssueSeverity.ERROR: 1,
    ir.IssueSeverity.WARNING: 2,
}


def _resolve_language(hass: HomeAssistant, language: str | None) -> str:
    """Resolve a translation language code from an LLMContext language."""
    if language and (stripped := language.strip()) and stripped != "*":
        return stripped
    return hass.config.language or "en"


def _format_issue(issue: ir.IssueEntry, translations: dict[str, str]) -> JsonObjectType:
    """Format an active IssueEntry for LLM consumption."""
    if TYPE_CHECKING:
        assert issue.is_fixable is not None
        assert issue.severity is not None
        assert issue.translation_key is not None

    result: JsonObjectType = {
        "domain": issue.domain,
        "issue_id": issue.issue_id,
        "severity": str(issue.severity).lower(),
        "is_fixable": issue.is_fixable,
        "created": issue.created.isoformat(),
    }
    if issue.issue_domain and issue.issue_domain != issue.domain:
        result["issue_domain"] = issue.issue_domain
    key_prefix = f"component.{issue.domain}.issues.{issue.translation_key}"
    placeholders = issue.translation_placeholders or {}
    for field in ("title", "description"):
        if value := translations.get(f"{key_prefix}.{field}"):
            for placeholder, replacement in placeholders.items():
                value = value.replace(f"{{{placeholder}}}", str(replacement))
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
        and (
            severity is None
            or (issue.severity is not None and str(issue.severity).lower() == severity)
        )
    ]
    issues.sort(
        key=lambda issue: (
            issue.dismissed_version is not None,
            _SEVERITY_ORDER.get(
                str(issue.severity).lower() if issue.severity is not None else "",
                len(_SEVERITY_ORDER),
            ),
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
                description=(
                    "Filter by issue severity. Allowed values: "
                    "'warning', 'error', 'critical'."
                ),
            ): probatio.All(str, probatio.Lower, probatio.In(_SEVERITIES)),
            probatio.Optional(
                "include_ignored",
                description=(
                    "Whether to include ignored (dismissed) issues in the results "
                    "(default: true)."
                ),
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


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the repairs LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[GetIssuesTool()])
