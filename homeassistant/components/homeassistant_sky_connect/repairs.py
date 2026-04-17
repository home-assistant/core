"""Repairs for the Home Assistant SkyConnect integration."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.homeassistant_hardware.repairs import (
    ISSUE_MULTI_PAN_MIGRATION,
    MultiPanMigrationRepairFlow,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .config_flow import HomeAssistantSkyConnectMultiPanOptionsFlowHandler


class SkyConnectMultiPanMigrationRepairFlow(
    MultiPanMigrationRepairFlow, HomeAssistantSkyConnectMultiPanOptionsFlowHandler
):
    """Multi-PAN migration repair flow for Home Assistant SkyConnect."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        super().__init__(config_entry)
        self._repair_config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Jump straight into the uninstall step."""
        return await self._async_step_start_migration(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a SkyConnect repair issue."""
    if issue_id.startswith(ISSUE_MULTI_PAN_MIGRATION) and data is not None:
        entry_id = cast(str, data.get("entry_id"))
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            return SkyConnectMultiPanMigrationRepairFlow(entry)

    return ConfirmRepairFlow()
