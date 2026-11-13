"""Config flow for the Ceiling Fan Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN

DOCS_URL = "https://www.home-assistant.io/integrations/ceiling_fan_infrared"


class CeilingFanIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ceiling Fan Infrared."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            if emitter_id := user_input.get(CONF_INFRARED_ENTITY_ID):
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
                return self.async_create_entry(
                    title=f"Ceiling fan via {self._emitter_name(emitter_id)}",
                    data={CONF_INFRARED_ENTITY_ID: emitter_id},
                )
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"docs_url": DOCS_URL},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            if emitter_id := user_input.get(CONF_INFRARED_ENTITY_ID):
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
                return self.async_update_reload_and_abort(
                    entry, data={CONF_INFRARED_ENTITY_ID: emitter_id}
                )
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=emitter_entity_ids,
                            )
                        ),
                    }
                ),
                entry.data,
            ),
            errors=errors,
        )

    @callback
    def _emitter_name(self, entity_id: str) -> str:
        """Return a friendly name for the infrared emitter entity."""
        if (entry := er.async_get(self.hass).async_get(entity_id)) is None:
            return entity_id
        return entry.name or entry.original_name or entity_id
