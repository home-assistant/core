"""Repairs for MQTT."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


class MQTTDeviceEntryMigration(RepairsFlow):
    """Handler to remove subentry for migrated MQTT device."""

    def __init__(self, entry_id: str, subentry_id: str, name: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id
        self.name = name

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            device_registry = dr.async_get(self.hass)
            subentry_device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.subentry_id)}
            )
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if TYPE_CHECKING:
                assert entry is not None
                assert subentry_device is not None
            self.hass.config_entries.async_remove_subentry(entry, self.subentry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"name": self.name},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert data is not None
    entry_id = data["entry_id"]
    subentry_id = data["subentry_id"]
    name = data["name"]
    if TYPE_CHECKING:
        assert isinstance(entry_id, str)
        assert isinstance(subentry_id, str)
        assert isinstance(name, str)
    return MQTTDeviceEntryMigration(
        entry_id=entry_id,
        subentry_id=subentry_id,
        name=name,
    )
