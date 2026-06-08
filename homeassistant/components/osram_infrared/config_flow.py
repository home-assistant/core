"""Config flow for the OSRAM infrared integration."""

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

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    get_unique_id,
)


class OsramIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OSRAM infrared."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)

        # An emitter is mandatory because the integration controls a light.
        # A receiver is optional and only improves assumed-state tracking.
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            emitter_entity_id = user_input[CONF_INFRARED_ENTITY_ID]

            await self.async_set_unique_id(get_unique_id(emitter_entity_id))
            self._abort_if_unique_id_configured()

            entity_registry = er.async_get(self.hass)
            entity_entry = entity_registry.async_get(emitter_entity_id)
            entity_name = (
                entity_entry.name or entity_entry.original_name or emitter_entity_id
                if entity_entry
                else emitter_entity_id
            )

            return self.async_create_entry(
                title=f"OSRAM light via {entity_name}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
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
            ),
        )
