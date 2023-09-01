"""Repairs implementation for supervisor integration."""

from collections.abc import Callable
from types import MethodType
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import get_addons_info, get_issues_info
from .const import (
    ISSUE_KEY_SYSTEM_DOCKER_CONFIG,
    PLACEHOLDER_KEY_COMPONENTS,
    PLACEHOLDER_KEY_REFERENCE,
    SupervisorIssueContext,
)
from .handler import HassioAPIError, async_apply_suggestion
from .issues import Issue, Suggestion

SUGGESTION_CONFIRMATION_REQUIRED = {"system_execute_reboot"}

EXTRA_PLACEHOLDERS = {
    "issue_mount_mount_failed": {
        "storage_url": "/config/storage",
    }
}


class SupervisorIssueRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _data: dict[str, Any] | None = None
    _issue: Issue | None = None

    def __init__(self, issue_id: str) -> None:
        """Initialize repair flow."""
        self._issue_id = issue_id
        super().__init__()

    @property
    def issue(self) -> Issue | None:
        """Get associated issue."""
        supervisor_issues = get_issues_info(self.hass)
        if not self._issue and supervisor_issues:
            self._issue = supervisor_issues.get_issue(self._issue_id)

        return self._issue

    @property
    def description_placeholders(self) -> dict[str, str] | None:
        """Get description placeholders for steps."""
        placeholders = {}
        if self.issue:
            placeholders = EXTRA_PLACEHOLDERS.get(self.issue.key, {})
            if self.issue.reference:
                placeholders |= {PLACEHOLDER_KEY_REFERENCE: self.issue.reference}

        return placeholders or None

    def _async_form_for_suggestion(self, suggestion: Suggestion) -> FlowResult:
        """Return form for suggestion."""
        return self.async_show_form(
            step_id=suggestion.key,
            data_schema=vol.Schema({}),
            description_placeholders=self.description_placeholders,
            last_step=True,
        )

    async def async_step_init(self, _: None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        # Out of sync with supervisor, issue is resolved or not fixable. Remove it
        if not self.issue or not self.issue.suggestions:
            return self.async_create_entry(data={})

        # All suggestions have the same logic: Apply them in supervisor,
        # optionally with a confirmation step. Generating the required handler for each
        # allows for shared logic but screens can still be translated per step id.
        for suggestion in self.issue.suggestions:
            setattr(
                self,
                f"async_step_{suggestion.key}",
                MethodType(self._async_step(suggestion), self),
            )

        if len(self.issue.suggestions) > 1:
            return self.async_show_menu(
                step_id="fix_menu",
                menu_options=[suggestion.key for suggestion in self.issue.suggestions],
                description_placeholders=self.description_placeholders,
            )

        # Always show a form for one suggestion to explain to user what's happening
        return self._async_form_for_suggestion(self.issue.suggestions[0])

    async def _async_step_apply_suggestion(
        self, suggestion: Suggestion, confirmed: bool = False
    ) -> FlowResult:
        """Handle applying a suggestion as a flow step. Optionally request confirmation."""
        if not confirmed and suggestion.key in SUGGESTION_CONFIRMATION_REQUIRED:
            return self._async_form_for_suggestion(suggestion)

        try:
            await async_apply_suggestion(self.hass, suggestion.uuid)
        except HassioAPIError:
            return self.async_abort(reason="apply_suggestion_fail")

        return self.async_create_entry(data={})

    @staticmethod
    def _async_step(suggestion: Suggestion) -> Callable:
        """Generate a step handler for a suggestion."""

        async def _async_step(
            self: SupervisorIssueRepairFlow, user_input: dict[str, str] | None = None
        ) -> FlowResult:
            """Handle a flow step for a suggestion."""
            # pylint: disable-next=protected-access
            return await self._async_step_apply_suggestion(
                suggestion, confirmed=user_input is not None
            )

        return _async_step


class DockerConfigIssueRepairFlow(SupervisorIssueRepairFlow):
    """Handler for docker config issue fixing flow."""

    @property
    def description_placeholders(self) -> dict[str, str] | None:
        """Get description placeholders for steps."""
        placeholders = {PLACEHOLDER_KEY_COMPONENTS: ""}
        supervisor_issues = get_issues_info(self.hass)
        if supervisor_issues and self.issue:
            addons = get_addons_info(self.hass) or {}
            components: list[str] = []
            for issue in supervisor_issues.issues:
                if issue.key == self.issue.key or issue.type != self.issue.type:
                    continue

                if issue.context == SupervisorIssueContext.CORE:
                    components.insert(0, "Home Assistant")
                elif issue.context == SupervisorIssueContext.ADDON:
                    components.append(
                        next(
                            (
                                info["name"]
                                for slug, info in addons.items()
                                if slug == issue.reference
                            ),
                            issue.reference or "",
                        )
                    )

            placeholders[PLACEHOLDER_KEY_COMPONENTS] = "\n- ".join(components)

        return placeholders


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    supervisor_issues = get_issues_info(hass)
    issue = supervisor_issues and supervisor_issues.get_issue(issue_id)
    if issue and issue.key == ISSUE_KEY_SYSTEM_DOCKER_CONFIG:
        return DockerConfigIssueRepairFlow(issue_id)

    return SupervisorIssueRepairFlow(issue_id)
