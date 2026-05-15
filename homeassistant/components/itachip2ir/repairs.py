"""Repair issues and repair flows for iTach IP2IR."""

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_CANNOT_CONNECT = "cannot_connect"
ISSUE_NO_IR_PORTS = "no_ir_ports"
ISSUE_INVALID_CONFIG = "invalid_config"


def async_create_repair_issue(
    hass: HomeAssistant,
    issue_id: str,
    *,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
    is_fixable: bool = False,
) -> None:
    """Create or update an iTach repair issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=is_fixable,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


def async_delete_repair_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete an iTach repair issue if present."""
    ir.async_delete_issue(hass, DOMAIN, issue_id)


class ReconfigureRepairFlow(RepairsFlow):
    """Informational repair flow for future fixable issues.

    Repair issues created by this integration are intentionally non-fixable by
    default because Home Assistant cannot automatically correct network reachability,
    physical IR connector mode, or stored-device configuration problems. The issue
    text points users to the actionable UI path: reconfigure or reload the config
    entry after correcting the device/network problem.
    """

    def __init__(self, issue_id: str, data: dict[str, Any] | None) -> None:
        """Initialize repair flow."""
        self._issue_id = issue_id
        self._data = data or {}

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Handle the first step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self,
        user_input: dict[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Confirm repair acknowledgement.

        This flow is kept for compatibility if a future issue is created as
        fixable. Current setup/runtime repair issues are informational because
        Home Assistant cannot automatically fix the underlying network, device,
        or physical connector problem.
        """
        if user_input is not None:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "entry_title": str(self._data.get("entry_title", "iTach IP2IR")),
                "host": str(self._data.get("host", "unknown")),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a repair flow for an issue."""
    return ReconfigureRepairFlow(issue_id, data)
