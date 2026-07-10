"""Repairs for the HomeKit integration."""

from copy import deepcopy
from typing import cast, override

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import CONF_ENTITY_CONFIG, TYPE_HEATER_COOLER


class HeaterCoolerCandidateRepairFlow(ConfirmRepairFlow):
    """Migrate an existing climate entity to the HeaterCooler accessory."""

    def __init__(self, entry: ConfigEntry, entity_id: str) -> None:
        """Create flow."""
        self.entry = entry
        self.entity_id = entity_id

    @override
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
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    # The only issue this integration creates always carries these keys.
    assert data is not None
    entry = hass.config_entries.async_get_entry(cast(str, data["entry_id"]))
    assert entry is not None
    return HeaterCoolerCandidateRepairFlow(entry, cast(str, data["entity_id"]))
