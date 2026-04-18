"""Repairs for Opower."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class UnsupportedUtilityFixFlow(RepairsFlow):
    """Handler for removing a configuration entry that uses an unsupported utility."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self._entry_id = data["entry_id"]
        self._placeholders = data.copy()
        self._placeholders.pop("entry_id")

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            await self.hass.config_entries.async_remove(self._entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm", description_placeholders=self._placeholders
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    assert issue_id.startswith("unsupported_utility")
    assert data
    return UnsupportedUtilityFixFlow(data)
