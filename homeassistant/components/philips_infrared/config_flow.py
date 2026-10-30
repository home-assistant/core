"""Config flow for Philips IR integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class PhilipsIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Philips IR."""

    VERSION = 1

    def _entity_name(self, entity_id: str) -> str:
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        return entry.name or entry.original_name or entity_id if entry else entity_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle emitter selection."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            emitter_id = user_input[CONF_INFRARED_ENTITY_ID]
            self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
            return self.async_create_entry(
                title=f"Philips TV via {self._entity_name(emitter_id)}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
        )
