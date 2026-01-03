"""Config flow for LG IR integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    InfraredProtocolType,
    async_get_entities,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        entities = async_get_entities(self.hass, protocols={InfraredProtocolType.NEC})
        if not entities:
            return self.async_abort(reason="no_emitters")

        valid_entity_ids = [entity.entity_id for entity in entities]

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_ENTITY_ID]

            await self.async_set_unique_id(f"lg_ir_{entity_id}")
            self._abort_if_unique_id_configured()

            # Get entity name for the title
            entity_name = next(
                (
                    entity.name or entity.entity_id
                    for entity in entities
                    if entity.entity_id == entity_id
                ),
                entity_id,
            )
            title = f"LG TV via {entity_name}"

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=valid_entity_ids,
                        )
                    ),
                }
            ),
        )
