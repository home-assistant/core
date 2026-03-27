"""Repairs for the Eve Online integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class MissingScopesRepairFlow(RepairsFlow):
    """Handler for missing OAuth scopes repair."""

    _entry_id: str
    _scopes: str

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step that triggers reauthentication."""
        if user_input is not None:
            if entry := self.hass.config_entries.async_get_entry(self._entry_id):
                entry.async_start_reauth(self.hass)
            return self.async_create_entry(data={})

        placeholders: dict[str, str] = {}
        if entry := self.hass.config_entries.async_get_entry(self._entry_id):
            placeholders["character"] = entry.title
        if self._scopes:
            placeholders["scopes"] = self._scopes

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert data is not None
    assert isinstance(data["entry_id"], str)

    flow = MissingScopesRepairFlow()
    flow._entry_id = data["entry_id"]  # noqa: SLF001
    flow._scopes = str(data.get("scopes", ""))  # noqa: SLF001
    return flow
