"""Config flow for OSRAM Infrared."""

from collections.abc import Collection
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

    def _async_validate_input(
        self,
        user_input: dict[str, Any],
        emitter_entity_ids: Collection[str],
        receiver_entity_ids: Collection[str],
    ) -> dict[str, str]:
        """Validate the user input."""
        errors: dict[str, str] = {}

        emitter_entity_id = user_input[CONF_IR_EMITTER_ENTITY_ID]
        if emitter_entity_id not in emitter_entity_ids:
            errors[CONF_IR_EMITTER_ENTITY_ID] = "cannot_connect"

        if (
            receiver_entity_id := user_input.get(CONF_IR_RECEIVER_ENTITY_ID)
        ) and receiver_entity_id not in receiver_entity_ids:
            errors[CONF_IR_RECEIVER_ENTITY_ID] = "cannot_connect"

        return errors

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

        errors: dict[str, str] = {}

        if user_input is not None:
            emitter_entity_id = user_input[CONF_IR_EMITTER_ENTITY_ID]

            self._async_abort_entries_match(
                {CONF_IR_EMITTER_ENTITY_ID: emitter_entity_id}
            )

            errors = self._async_validate_input(
                user_input,
                emitter_entity_ids,
                receiver_entity_ids,
            )

            if not errors:
                return self.async_create_entry(
                    title=self._async_get_entry_title(emitter_entity_id),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IR_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=list(emitter_entity_ids),
                        )
                    ),
                    vol.Optional(CONF_IR_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=list(receiver_entity_ids),
                        )
                    ),
                }
            ),
            errors=errors,
        )
