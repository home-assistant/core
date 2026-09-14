"""The repairs integration."""

from typing import Any, cast, overload, override

import probatio

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms

from .const import DOMAIN
from .models import RepairsFlow, RepairsFlowContext, RepairsFlowResult, RepairsProtocol


class ConfirmRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow without any side effects."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=description_placeholders,
        )


# Sentinel to handle overload missing arg
class _MISSING_ARG:
    pass


class _DeprecatedIssueIdDict[_VT](dict[str, _VT]):
    """Dict to detect use of `issue_id` in async_step_init by a RepairFlow."""

    def __init__(self, integration_domain: str, data: dict[str, _VT]) -> None:
        super().__init__(data)
        self._integration_domain = integration_domain

    @override
    def __getitem__(self, key: str) -> _VT:
        """Deprecation warning on issue_id key access."""
        if key == "issue_id":
            self._report_issue_id_usage("accesses")
        return super().__getitem__(key)

    @overload
    def get(self, key: str, default: None = None, /) -> _VT | None: ...
    @overload
    def get(self, key: str, default: _VT, /) -> _VT: ...
    @overload
    def get[_T](self, key: str, default: _T, /) -> _VT | _T: ...

    @override
    def get[_T](self, key: str, default: _T | None = None, /) -> _VT | _T | None:
        """Deprecation warning on issue_id key access."""
        if key == "issue_id":
            self._report_issue_id_usage("gets")
        return super().get(key, default)

    @overload
    def pop(self, key: str, /) -> _VT: ...
    @overload
    def pop(self, key: str, default: _VT, /) -> _VT: ...
    @overload
    def pop[_T](self, key: str, default: _T, /) -> _T: ...

    @override
    def pop[_T](
        self, key: str, default: _T | _VT | _MISSING_ARG = _MISSING_ARG(), /
    ) -> _VT | _T:
        """Deprecation warning on issue_id key access."""
        if key == "issue_id":
            self._report_issue_id_usage("pops")
        if isinstance(default, _MISSING_ARG):
            return super().pop(key)
        return super().pop(key, default)

    def _report_issue_id_usage(self, method: str) -> None:
        report_usage(
            f"{method} `issue_id` from `user_input` in `async_step_init` of a `RepairsFlow` "
            "instead of `self.issue_id`",
            breaks_in_ha_version="2028.10.0",
            integration_domain=self._integration_domain,
        )


class RepairsFlowManager(
    data_entry_flow.FlowManager[RepairsFlowContext, RepairsFlowResult, str]
):
    """Manage repairs flows."""

    @override
    async def async_init(
        self,
        handler: str,
        *,
        context: RepairsFlowContext | None = None,
        data: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Override to ensure appropriate context is set in the flow result."""
        _context: RepairsFlowContext = context or {}
        if "issue_id" not in _context and data is not None and "issue_id" in data:
            # fallback for custom integrations
            _context |= {"issue_id": data["issue_id"]}
            report_usage(
                "initiates a repair flow by passing `issue_id` via `data` rather than `context`",
                breaks_in_ha_version="2028.10.0",
                integration_domain=handler,
            )
        if "issue_id" in _context:
            # interim compatibility fallback for custom integrations that may expect
            # "issue_id" in user_input of async_step_init
            data = cast(
                dict[
                    str,
                    Any,
                ],
                _DeprecatedIssueIdDict(handler, data)
                if data is not None
                else _DeprecatedIssueIdDict(handler, {}),
            )
            data["issue_id"] = _context["issue_id"]
        return await super().async_init(handler, context=_context, data=data)

    @override
    async def async_create_flow(
        self,
        handler_key: str,
        *,
        context: RepairsFlowContext | None = None,
        data: dict[str, Any] | None = None,
    ) -> RepairsFlow:
        """Create a flow. platform is a repairs module."""
        if context is None or "issue_id" not in context:
            raise KeyError("issue_id was not set in context")
        issue_id = context["issue_id"]

        issue_registry = ir.async_get(self.hass)
        issue = issue_registry.async_get_issue(handler_key, issue_id)
        if issue is None or not issue.is_fixable:
            raise data_entry_flow.UnknownStep(
                f"issue id {issue_id} is {'not found' if issue is None else 'not fixable'}"
            )

        platforms: LazyIntegrationPlatforms[RepairsProtocol] = self.hass.data[DOMAIN][
            "platforms"
        ]
        if (platform := await platforms.async_get_platform(handler_key)) is None:
            flow: RepairsFlow = ConfirmRepairFlow()
        else:
            flow = await platform.async_create_fix_flow(self.hass, issue_id, issue.data)

        flow.data = issue.data
        return flow

    @override
    async def async_finish_flow(
        self,
        flow: data_entry_flow.FlowHandler[RepairsFlowContext, RepairsFlowResult, str],
        result: RepairsFlowResult,
    ) -> RepairsFlowResult:
        """Complete a fix flow.

        This method is called when a flow step returns FlowResultType.ABORT or
        FlowResultType.CREATE_ENTRY.
        """
        if result.get("type") is not data_entry_flow.FlowResultType.ABORT:
            ir.async_delete_issue(self.hass, flow.handler, flow.context["issue_id"])
        return result


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Initialize repairs."""
    hass.data[DOMAIN]["flow_manager"] = RepairsFlowManager(hass)
    hass.data[DOMAIN]["platforms"] = LazyIntegrationPlatforms(
        hass, DOMAIN, _process_repairs_platform
    )


@callback
def _process_repairs_platform(
    hass: HomeAssistant, integration_domain: str, platform: RepairsProtocol
) -> RepairsProtocol:
    """Process a repairs platform."""
    if not hasattr(platform, "async_create_fix_flow"):
        raise HomeAssistantError(f"Invalid repairs platform {platform}")
    return platform
