"""Config flow for OSRAM Infrared."""

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_IR_EMITTER_ENTITY_ID, CONF_IR_RECEIVER_ENTITY_ID, DOMAIN


class OsramIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OSRAM Infrared."""

    VERSION = 2

    def _async_has_infrared_entities(self) -> bool:
        """Return if any infrared entities are available."""
        entity_registry = er.async_get(self.hass)

        return any(
            entity_entry.domain == INFRARED_DOMAIN
            for entity_entry in entity_registry.entities.values()
        )

    def _async_get_entry_title(self, emitter_entity_id: str) -> str:
        """Return config entry title for the selected emitter."""
        entity_registry = er.async_get(self.hass)
        entity_entry = entity_registry.async_get(emitter_entity_id)

        if entity_entry is None:
            emitter_name = emitter_entity_id
        else:
            emitter_name = (
                entity_entry.name
                or entity_entry.original_name
                or entity_entry.entity_id
            )

        return f"OSRAM light via {emitter_name}"

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            emitter_entity_id = user_input[CONF_IR_EMITTER_ENTITY_ID]

            self._async_abort_entries_match(
                {CONF_IR_EMITTER_ENTITY_ID: emitter_entity_id}
            )

            return self.async_create_entry(
                title=self._async_get_entry_title(emitter_entity_id),
                data=user_input,
            )

        if not self._async_has_infrared_entities():
            return self.async_abort(reason="no_infrared_emitters")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IR_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(domain=INFRARED_DOMAIN)
                    ),
                    vol.Optional(CONF_IR_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(domain=INFRARED_DOMAIN)
                    ),
                }
            ),
        )
