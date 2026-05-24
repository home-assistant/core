"""Repairs platform for the Min/Max integration."""

from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.group import (
    CONF_ENTITIES,
    CONF_HIDE_MEMBERS,
    DOMAIN as GROUP_DOMAIN,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN


class MigrateToGroupSensorFlow(RepairsFlow):
    """Repair flow to migrate Min/Max helper to Group sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_migrate()

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the migration step of a fix flow."""
        entity_reg = er.async_get(self.hass)
        old_entity = entity_reg.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, self.entry.entry_id
        )
        if not old_entity:
            return self.async_abort(reason="entity_not_found")

        if user_input is not None:
            config = dict(self.entry.options)
            config[CONF_ENTITIES] = config.pop(CONF_ENTITY_IDS)
            config.pop(CONF_ROUND_DIGITS)
            # Set group sensor defaults
            config[CONF_HIDE_MEMBERS] = False
            # config[CONF_IGNORE_NON_NUMERIC] = False
            # config[CONF_GROUP_TYPE] = SENSOR_DOMAIN
            config["old_config_entry_id"] = self.entry.entry_id

            import_result = await self.hass.config_entries.flow.async_init(
                GROUP_DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config,
            )

            if import_result["type"] != FlowResultType.CREATE_ENTRY:
                if TYPE_CHECKING:
                    assert import_result["description_placeholders"]
                return self.async_abort(
                    reason="could_not_import",
                    description_placeholders={
                        "error": import_result["description_placeholders"]["error"]
                    },
                )
            return self.async_create_entry(data={})

        entity_info = entity_reg.async_get(old_entity)
        if TYPE_CHECKING:
            assert entity_info
        title = er.async_get_full_entity_name(self.hass, entity_info)

        return self.async_show_form(
            step_id="migrate",
            data_schema=vol.Schema({}),
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
        if TYPE_CHECKING:
            assert entry
        return MigrateToGroupSensorFlow(entry)

    return ConfirmRepairFlow()
