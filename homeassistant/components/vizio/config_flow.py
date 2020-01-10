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
from homeassistant.core import callback

from . import validate_auth
from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


VIZIO_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required(CONF_HOST, default=""): str,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.All(
        str, vol.Lower, vol.In(["tv", "soundbar"])
    ),
    vol.Optional(CONF_ACCESS_TOKEN, default=""): str,
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=10)
    ),
}


class VizioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vizio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return VizioOptionsConfigFlow(config_entry)

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
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
                    if not await VizioAsync.validate_config(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    ):
                        errors["base"] = "invalid_setup"
                except vol.Invalid:
                    errors["base"] = "tv_needs_token"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(VIZIO_SCHEMA), errors=errors
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""
        # Check if new config entry matches any existing config entries
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == import_config[CONF_HOST] and entry.data[
                CONF_NAME
            ] == import_config.get(CONF_NAME):
                return self.async_abort(reason="already_setup")
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.error(
                    "Vizio entity 'media_player.%s' already configured with host '%s' so entity 'media_player.%s' with host '%s' can't be imported.",
                    entry.data[CONF_NAME],
                    entry.data[CONF_HOST],
                    import_config[CONF_NAME],
                    import_config[CONF_HOST],
                )
                return self.async_abort(reason="host_exists")
            if entry.data[CONF_NAME] == import_config.get(CONF_NAME):
                _LOGGER.error(
                    "Vizio entity 'media_player.%s' already configured with host '%s' so entity 'media_player.%s' with host '%s' can't be imported.",
                    entry.data[CONF_NAME],
                    entry.data[CONF_HOST],
                    import_config[CONF_NAME],
                    import_config[CONF_HOST],
                )
                return self.async_abort(reason="name_exists")

        return await self.async_step_user(user_input=import_config)


class VizioOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry):
        """Initialize vizio options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the vizio options."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        options = {
            vol.Optional(
                CONF_VOLUME_STEP,
                default=self.config_entry.options.get(
                    CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10))
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
