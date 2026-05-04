"""Repairs platform for the Workday integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, cast

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.group import (
    CONF_ENTITIES,
    CONF_GROUP_TYPE,
    CONF_HIDE_MEMBERS,
    CONF_IGNORE_NON_NUMERIC,
    DOMAIN as GROUP_DOMAIN,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN


class MigrateToGroupSensorFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_migrate()

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the migration step of a fix flow."""
        errors: dict[str, str] = {}
        entity_reg = er.async_get(self.hass)
        old_entity = entity_reg.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, self.entry.entry_id
        )
        assert old_entity

        if user_input is not None:
            config = dict(self.entry.options)
            config[CONF_ENTITIES] = config.pop(CONF_ENTITY_IDS)
            config.pop(CONF_ROUND_DIGITS)
            # Set group sensor defaults
            config[CONF_HIDE_MEMBERS] = False
            config[CONF_IGNORE_NON_NUMERIC] = False
            config[CONF_GROUP_TYPE] = SENSOR_DOMAIN

            new_config_entry = ConfigEntry(
                data={},
                discovery_keys=MappingProxyType({}),
                domain=GROUP_DOMAIN,
                minor_version=1,
                options=config,
                source=SOURCE_USER,
                subentries_data=[],
                title=self.entry.title,
                unique_id=None,
                version=1,
            )

            await self.hass.config_entries.async_unload_platforms(
                self.entry, [SENSOR_DOMAIN]
            )
            await self.hass.config_entries.async_unload(self.entry.entry_id)
            await self.hass.config_entries.async_add(new_config_entry)
            if old_entity:
                entity_reg.async_update_entity_platform(
                    old_entity,
                    GROUP_DOMAIN,
                    new_config_entry_id=new_config_entry.entry_id,
                )
            await self.hass.config_entries.async_remove(self.entry.entry_id)

            return self.async_create_entry(data={})

        entity_info = entity_reg.async_get(old_entity)
        assert entity_info
        title = er.async_get_full_entity_name(self.hass, entity_info)

        return self.async_show_form(
            step_id="migrate",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"title": title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    if data and (entry_id := data.get("entry_id")):
        entry_id = cast(str, entry_id)
        entry = hass.config_entries.async_get_entry(entry_id)
        assert entry
        return MigrateToGroupSensorFlow(entry)

    return ConfirmRepairFlow()
