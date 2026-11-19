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

from .const import CONF_INFRARED_ENTITY_ID, CONF_INFRARED_ENTITY_UUID, DOMAIN

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
            if emitter_id := self._resolve_emitter_id(
                emitter_entity_ids, user_input.get(CONF_INFRARED_ENTITY_ID)
            ):
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
                return self.async_create_entry(
                    title=f"Ceiling fan via {self._emitter_name(emitter_id)}",
                    data=self._entry_data(emitter_id),
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
            if emitter_id := self._resolve_emitter_id(
                emitter_entity_ids, user_input.get(CONF_INFRARED_ENTITY_ID)
            ):
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
                return self.async_update_reload_and_abort(
                    entry, data=self._entry_data(emitter_id)
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
    def _resolve_emitter_id(
        self, emitter_entity_ids: list[str], selection: str | None
    ) -> str | None:
        """Resolve a selection to a currently loaded emitter entity ID.

        The entity selector also accepts an entity registry UUID, so resolve the
        selection and confirm it is an emitter before storing it. Storing anything
        else would leave the fan unavailable and slip past the duplicate check.
        """
        if not selection:
            return None
        entity_id = er.async_resolve_entity_id(er.async_get(self.hass), selection)
        if entity_id is None or entity_id not in emitter_entity_ids:
            return None
        return entity_id

    @callback
    def _entry_data(self, entity_id: str) -> dict[str, Any]:
        """Return the config entry data for an emitter.

        The registry UUID is stored alongside the entity ID, so the emitter is
        still found after a rename that happens while the entry is unloaded.
        Emitters without a registry entry only have an entity ID to store.
        """
        data: dict[str, Any] = {CONF_INFRARED_ENTITY_ID: entity_id}
        if (registry_entry := er.async_get(self.hass).async_get(entity_id)) is not None:
            data[CONF_INFRARED_ENTITY_UUID] = registry_entry.id
        return data

    @callback
    def _emitter_name(self, entity_id: str) -> str:
        """Return a friendly name for the infrared emitter entity."""
        if (entry := er.async_get(self.hass).async_get(entity_id)) is None:
            return entity_id
        return entry.name or entry.original_name or entity_id
