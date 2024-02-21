"""Repairs platform for the System Monitor integration."""

from __future__ import annotations

from typing import Any, cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


class ProcessFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry, processes: list[str]) -> None:
        """Create flow."""
        super().__init__()
        self.entry = entry
        self._processes = processes

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_migrate_process_sensor()

    async def async_step_migrate_process_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the options step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="migrate_process_sensor",
                description_placeholders={"processes": ", ".join(self._processes)},
            )

        # Migration has copied the sensors to binary sensors
        # Pop the sensors to repair and remove entities
        new_options: dict[str, Any] = self.entry.options.copy()
        new_options.pop(SENSOR_DOMAIN)

        entity_reg = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(entity_reg, self.entry.entry_id)
        for entry in entries:
            if entry.entity_id.startswith("sensor.") and entry.unique_id.startswith(
                "process_"
            ):
                entity_reg.async_remove(entry.entity_id)

        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    entry = None
    if data and (entry_id := data.get("entry_id")):
        entry_id = cast(str, entry_id)
        processes: list[str] = data["processes"]
        entry = hass.config_entries.async_get_entry(entry_id)
        assert entry
        return ProcessFixFlow(entry, processes)

    return ConfirmRepairFlow()
