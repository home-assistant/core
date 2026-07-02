"""Config flow for the Virtual Remote integration."""

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
    infrared_entity_field_with_current,
    infrared_entity_selector,
    normalize_remote_id,
    virtual_remotes_from_config_entry,
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
                remote_id = normalize_remote_id(name)
                await self.async_set_unique_id(remote_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_REMOTE_ID: remote_id,
                        CONF_REMOTE_NAME: name,
                        CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                    },
                    options={},
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

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the first virtual remote."""
        entry = self._get_reconfigure_entry()
        virtual_remotes = virtual_remotes_from_config_entry(entry)
        infrared_entities = available_infrared_entities(self.hass)

        if not virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        first_remote = virtual_remotes[0]
        current_name = str(first_remote[CONF_REMOTE_NAME])
        current_entity_id = str(first_remote[CONF_INFRARED_ENTITY_ID])

        if not infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"

            if (
                infrared_entity_id not in infrared_entities
                and infrared_entity_id != current_entity_id
            ):
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                first_remote[CONF_REMOTE_NAME] = name
                first_remote[CONF_INFRARED_ENTITY_ID] = infrared_entity_id

                data_updates: dict[str, Any] = {}
                options = dict(entry.options)

                if CONF_REMOTE_ID in entry.data:
                    data_updates = {
                        CONF_REMOTE_NAME: name,
                        CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                    }
                else:
                    options[CONF_VIRTUAL_REMOTES] = virtual_remotes

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                    options=options,
                )

        remote_name_default = (
            str(user_input.get(CONF_REMOTE_NAME, current_name))
            if user_input
            else current_name
        )
        infrared_entity_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, current_entity_id))
            if user_input
            else current_entity_id
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REMOTE_NAME,
                        default=remote_name_default,
                    ): str,
                    infrared_entity_field_with_current(
                        infrared_entity_default,
                        infrared_entities,
                    ): infrared_entity_selector(
                        infrared_entities,
                        current_entity_id=current_entity_id,
                    ),
                }
            ),
            errors=errors,
        )
