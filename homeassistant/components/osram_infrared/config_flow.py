"""Config flow for the Osram IR integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_INFRARED_ENTITY_ID, CONF_INFRARED_RECEIVER_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OsramIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Osram IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        errors: dict[str, str] = {}

        if user_input is not None:
            if entity_id := user_input.get(CONF_INFRARED_ENTITY_ID) or user_input.get(
                CONF_INFRARED_RECEIVER_ENTITY_ID
            ):
                await self.async_set_unique_id(f"osram_ir_light_{entity_id}")
                self._abort_if_unique_id_configured()

                # Get entity name for the title
                ent_reg = er.async_get(self.hass)
                entry = ent_reg.async_get(entity_id)
                entity_name = (
                    entry.name or entry.original_name or entity_id
                    if entry
                    else entity_id
                )
                title = f"Osram light via {entity_name}"

                return self.async_create_entry(title=title, data=user_input)

            errors["base"] = "missing_infrared_entity"

        schema_dict: dict[vol.Marker, Any] = {
            vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=emitter_entity_ids,
                )
            ),
            vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=receiver_entity_ids,
                )
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
