"""Repairs for the HomeKit integration."""

from copy import deepcopy

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import CONF_ENTITY_CONFIG, ISSUE_HEATER_COOLER_CANDIDATE, TYPE_HEATER_COOLER


class HeaterCoolerCandidateRepairFlow(RepairsFlow):
    """Migrate an existing climate entity to the HeaterCooler accessory."""

    def __init__(self, entry: ConfigEntry, entity_id: str) -> None:
        """Create flow."""
        self.entry = entry
        self.entity_id = entity_id

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
            options = deepcopy(dict(self.entry.options))
            entity_config = options.setdefault(CONF_ENTITY_CONFIG, {})
            entity_config.setdefault(self.entity_id, {})[CONF_TYPE] = TYPE_HEATER_COOLER
            # The update listener reloads the bridge with the new options.
            self.hass.config_entries.async_update_entry(self.entry, options=options)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "entity_id": self.entity_id,
                "bridge": self.entry.title,
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        issue_id.startswith(f"{ISSUE_HEATER_COOLER_CANDIDATE}_")
        and data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(entity_id := data.get("entity_id"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id))
    ):
        return HeaterCoolerCandidateRepairFlow(entry, entity_id)

    return ConfirmRepairFlow()
