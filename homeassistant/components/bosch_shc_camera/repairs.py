"""Bosch Smart Home Camera — Repairs Fix Flows.

Combines the firmware-update-available Repairs issue (__init__.py,
_refresh_firmware_update_issues) with the install action (coordinator's
async_install_firmware, also used by update.py's Install button) — pressing
"Fix" on the Repairs issue installs the update directly instead of only
pointing the user at a separate button elsewhere.
"""

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class FirmwareUpdateRepairFlow(RepairsFlow):
    """Confirm, then install the pending firmware update for one camera."""

    def __init__(self, coordinator: Any, cam_id: str) -> None:
        """Initialize the firmware-update repair flow."""
        self._coordinator = coordinator
        self._cam_id = cam_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user confirming the firmware install."""
        if self._coordinator is None:
            return self.async_abort(reason="install_failed")
        if user_input is not None:
            try:
                await self._coordinator.async_install_firmware(self._cam_id)
            except HomeAssistantError:
                return self.async_abort(reason="install_failed")
            return self.async_create_entry(data={})

        fw: dict[str, Any] = self._coordinator.firmware_cache.get(self._cam_id, {})
        cam_title: str = (
            (self._coordinator.data or {})
            .get(self._cam_id, {})
            .get("info", {})
            .get("title", self._cam_id)
        )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "camera": cam_title,
                "current": fw.get("current") or "?",
                "latest": fw.get("update") or "?",
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Return the fix flow for a given Repairs issue.

    Only `firmware_update_available_*` issues are fixable today — `data`
    carries the `cam_id` stashed at ir.async_create_issue() time.
    """
    cam_id = str((data or {}).get("cam_id", ""))
    coordinator = None
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.runtime_data is not None:
            coordinator = entry.runtime_data
            break
    return FirmwareUpdateRepairFlow(coordinator, cam_id)
