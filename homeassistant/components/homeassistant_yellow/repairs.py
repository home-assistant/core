"""Repairs for the Home Assistant Yellow integration."""

from typing import cast

from homeassistant.components.homeassistant_hardware.repair_helpers import (
    ISSUE_MULTI_PAN_MIGRATION,
    MultiPanMigrationRepairFlow,
)
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .config_flow import HomeAssistantYellowMultiPanOptionsFlowHandler


class YellowMultiPanMigrationRepairFlow(
    MultiPanMigrationRepairFlow, HomeAssistantYellowMultiPanOptionsFlowHandler
):
    """Multi-PAN migration repair flow for Home Assistant Yellow."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        HomeAssistantYellowMultiPanOptionsFlowHandler.__init__(self, hass, config_entry)
        self._repair_config_entry = config_entry

    async def async_step_main_menu(  # type: ignore[override]
        self, _: None = None
    ) -> RepairsFlowResult:
        """Jump straight into the uninstall step."""
        return await self._async_step_start_migration()


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a Yellow repair issue."""
    if issue_id.startswith(ISSUE_MULTI_PAN_MIGRATION) and data is not None:
        entry_id = cast(str, data["entry_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            return YellowMultiPanMigrationRepairFlow(hass, entry)

    return ConfirmRepairFlow()
