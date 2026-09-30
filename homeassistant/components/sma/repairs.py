"""Repairs for the SMA integration."""

from typing import Any

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .config_flow import OPTIONS_SCHEMA, validate_modbus


class ModbusUnreachableRepairFlow(RepairsFlow):
    """Let the user correct or turn off Modbus after it became unreachable."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Start the flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show the Modbus settings and check them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await validate_modbus(self._entry.data[CONF_HOST], user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._entry, options=user_input
                )
                self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or self._entry.options
            ),
            description_placeholders={"name": self._entry.title},
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow that fixes an SMA issue."""
    if (
        data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id))
    ):
        return ModbusUnreachableRepairFlow(entry)
    return ConfirmRepairFlow()
