"""Config flow for the Daikin Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)


class DaikinIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Daikin Infrared."""

    VERSION = 1

    def _entity_name(self, entity_id: str) -> str:
        """Return the name an entity is shown with, falling back to its ID."""
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return entity_id
        return entry.name or entry.original_name or entity_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle emitter and receiver selection."""
        if not (emitters := async_get_emitters(self.hass)):
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            emitter_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
            self._async_abort_entries_match(
                {CONF_INFRARED_EMITTER_ENTITY_ID: emitter_id}
            )
            if receiver_id := user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
                self._async_abort_entries_match(
                    {CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id}
                )

            return self.async_create_entry(
                title=f"Daikin AC via {self._entity_name(emitter_id)}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN, include_entities=emitters
                        )
                    ),
                    probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=async_get_receivers(self.hass),
                        )
                    ),
                }
            ),
        )
