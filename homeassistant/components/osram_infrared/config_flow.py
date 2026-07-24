"""Config flow for OSRAM Infrared."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_IR_EMITTER_ENTITY_ID, CONF_IR_RECEIVER_ENTITY_ID, DOMAIN


class OsramIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OSRAM Infrared."""

    VERSION = 1

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            emitter_entity_id = user_input[CONF_IR_EMITTER_ENTITY_ID]
            self._async_abort_entries_match(
                {CONF_IR_EMITTER_ENTITY_ID: emitter_entity_id}
            )

            ent_reg = er.async_get(self.hass)
            entry = ent_reg.async_get(emitter_entity_id)
            title_entity_name = (
                (entry.name or entry.original_name or emitter_entity_id)
                if entry
                else emitter_entity_id
            )
            title = f"OSRAM light via {title_entity_name}"

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IR_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    vol.Optional(CONF_IR_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=receiver_entity_ids,
                        )
                    ),
                }
            ),
        )
