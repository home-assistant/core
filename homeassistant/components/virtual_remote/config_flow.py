"""Config flow for the Virtual Remote integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from .helpers import (
    available_infrared_entities,
    infrared_entity_field,
    infrared_entity_selector,
    unique_remote_id,
)
from .options_flow import VirtualRemoteOptionsFlow


class VirtualRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Virtual Remote."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> VirtualRemoteOptionsFlow:
        """Create the options flow."""
        return VirtualRemoteOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        infrared_entities = available_infrared_entities(self.hass)

        if not infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"

            if infrared_entity_id not in infrared_entities:
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                return self.async_create_entry(
                    title="Virtual Remote",
                    data={},
                    options={
                        CONF_VIRTUAL_REMOTES: [
                            {
                                CONF_REMOTE_ID: unique_remote_id(name, []),
                                CONF_REMOTE_NAME: name,
                                CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                            }
                        ],
                    },
                )

        remote_name_default = (
            str(user_input.get(CONF_REMOTE_NAME, "")) if user_input else ""
        )
        infrared_entity_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, "")) if user_input else ""
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REMOTE_NAME,
                        default=remote_name_default,
                    ): str,
                    infrared_entity_field(
                        infrared_entity_default,
                        infrared_entities,
                    ): infrared_entity_selector(infrared_entities),
                }
            ),
            errors=errors,
        )
