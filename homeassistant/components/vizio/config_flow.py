"""Config flow for Vizio."""

import logging
from typing import Any, Dict

from pyvizio import VizioAsync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.data_entry_flow import AbortFlow

from . import validate_auth
from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def update_schema_defaults(input_dict: Dict[str, Any]) -> vol.Schema:
    """Update schema defaults based on user input/config dict. Retains info already provided for future form views."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_HOST, default=input_dict.get(CONF_HOST)): str,
            vol.Optional(
                CONF_DEVICE_CLASS,
                default=input_dict.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            ): vol.All(str, vol.Lower, vol.In(["tv", "soundbar"])),
            vol.Optional(
                CONF_ACCESS_TOKEN, default=input_dict.get(CONF_ACCESS_TOKEN, "")
            ): str,
            vol.Optional(
                CONF_VOLUME_STEP,
                default=input_dict.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        }
    )


class VizioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vizio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize config flow."""
        self.import_schema = None
        self.user_schema = None

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(unique_id=user_input[CONF_HOST])

            # Store current values in case setup fails and user needs to edit
            self.user_schema = update_schema_defaults(user_input)

            # Check if new config entry matches any existing config entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    errors[CONF_HOST] = "host_exists"
                    break

                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            if not errors:
                try:
                    # Ensure schema passes custom validation, otherwise catch exception and add error
                    validate_auth(user_input)

                    # Ensure config is valid for a device
                    if not await VizioAsync.validate_ha_config(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    ):
                        errors["base"] = "no_connect"
                except vol.Invalid:
                    errors["base"] = "tv_needs_token"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = self.user_schema or self.import_schema or update_schema_defaults({})

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""
        # Check if new config entry matches any existing config entries
        try:
            if await self.async_set_unique_id(
                unique_id=import_config[CONF_HOST], raise_on_progress=True
            ):
                return self.async_abort(reason="already_setup")
        except AbortFlow:
            return self.async_abort(reason="already_in_progress")

        # Since unique ID is set to serial number after initialization, also need to check host and name
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == import_config[CONF_HOST] and entry.data[
                CONF_NAME
            ] == import_config.get(CONF_NAME):
                return self.async_abort(reason="already_setup")

        # Store import values in case setup fails so user can see error
        self.import_schema = update_schema_defaults(import_config)

        return await self.async_step_user(user_input=import_config)
