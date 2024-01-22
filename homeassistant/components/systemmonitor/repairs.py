"""Repairs platform for the System Monitor integration."""

from __future__ import annotations

from typing import Any, cast

from homeassistant import data_entry_flow
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class ProcessFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry, processes: list[str]) -> None:
        """Create flow."""
        self.entry = entry
        self._processes = processes
        super().__init__()

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
        options = dict(self.entry.options)
        resources: list[str] | None = options.get("resources")
        processes: dict[str, list[str]] | None = options.get(SENSOR_DOMAIN)
        new_options: dict[str, Any] = {}
        if processes:
            new_options[BINARY_SENSOR_DOMAIN] = processes
        if resources:
            new_options["resources"] = resources

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
