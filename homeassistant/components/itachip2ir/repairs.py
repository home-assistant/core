"""Repairs support for the iTach IP2IR integration."""

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_CANNOT_CONNECT, ISSUE_INVALID_CONFIG, ISSUE_NO_IR_PORTS

_DEFAULT_PLACEHOLDERS = {
    "entry_title": "iTach IP2IR",
    "host": "unknown",
}


def async_create_repair_issue(
    hass: HomeAssistant,
    issue_id: str,
    *,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
    is_fixable: bool = False,
) -> None:
    """Create a Home Assistant repair issue for the integration."""
    translation_placeholders: dict[str, str] | None = placeholders

    if translation_key in {ISSUE_CANNOT_CONNECT, ISSUE_NO_IR_PORTS}:
        translation_placeholders = {
            **_DEFAULT_PLACEHOLDERS,
            **(placeholders or {}),
        }
    elif translation_key == ISSUE_INVALID_CONFIG and placeholders is not None:
        translation_placeholders = {
            "entry_title": placeholders.get("entry_title", "iTach IP2IR"),
            "error": placeholders.get("error", "unknown"),
        }

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=is_fixable,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
        issue_domain=DOMAIN,
    )


def async_delete_repair_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a Home Assistant repair issue for the integration."""
    ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a repair flow for an iTach IP2IR issue."""
    return ReconfigureRepairFlow(issue_id, data)


class ReconfigureRepairFlow(RepairsFlow):
    """Repair flow that guides the user to reconfigure or reload the entry."""

    def __init__(self, issue_id: str, data: dict[str, Any] | None) -> None:
        """Initialize the repair flow."""
        self._issue_id = issue_id
        self._placeholders = {
            **_DEFAULT_PLACEHOLDERS,
            **(data or {}),
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Handle the initial repair step."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Confirm that the user has handled the repair issue."""
        if user_input is not None:
            async_delete_repair_issue(self.hass, self._issue_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self._placeholders,
        )
