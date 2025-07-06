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
    """Handler to migrate device from subentry to main entry and reload."""

    def __init__(
        self, entry_id: str, subentry_id: str, name: str, migration_type: str
    ) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id
        self.name = name
        self.migration_type = migration_type

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None and self.migration_type == "subentry_migration_yaml":
            # Via YAML the device was already registered and bound to the entry,
            # so it is safe to remove the subentry from here.
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
        if (
            user_input is not None
            and self.migration_type == "subentry_migration_discovery"
        ):
            # The device offered via discovery was already set up through the subentry,
            # so we need to update the device before removing the subentry and reload.
            device_registry = dr.async_get(self.hass)
            subentry_device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.subentry_id)}
            )
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if TYPE_CHECKING:
                assert entry is not None
                assert subentry_device is not None
            device_registry.async_update_device(
                subentry_device.id,
                remove_config_entry_id=self.entry_id,
                remove_config_subentry_id=self.subentry_id,
                add_config_entry_id=self.entry_id,
            )
            self.hass.config_entries.async_remove_subentry(entry, self.subentry_id)
            self.hass.config_entries.async_schedule_reload(self.entry_id)
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
    migration_type = data["migration_type"]
    if TYPE_CHECKING:
        assert isinstance(entry_id, str)
        assert isinstance(subentry_id, str)
        assert isinstance(name, str)
        assert isinstance(migration_type, str)
    return MQTTDeviceEntryMigration(
        entry_id=entry_id,
        subentry_id=subentry_id,
        name=name,
        migration_type=migration_type,
    )
