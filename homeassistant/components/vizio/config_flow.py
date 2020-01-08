"""Config flow for Vizio."""

import logging
from typing import Any, Dict, Optional

from pyvizio import Vizio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)

from . import validate_auth
from .const import (
    CONF_CONTEXT,
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def vizio_schema(self, defaults: Optional[Dict[str, any]] = None) -> vol.Schema:
    """Return vol schema with expected defaults for blank form, retain what was previously filled in on error, or prefill data obtained via zeroconf."""

    if not defaults:
        defaults = {}

    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST)): str,
            vol.Optional(
                CONF_DEVICE_CLASS,
                default=defaults.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            ): vol.All(str, vol.Lower, vol.In(["tv", "soundbar"])),
            vol.Optional(
                CONF_ACCESS_TOKEN, default=defaults.get(CONF_ACCESS_TOKEN)
            ): str,
            vol.Optional(
                CONF_VOLUME_STEP,
                default=defaults.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        }
    )


class VizioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vizio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""

        errors = {}
        defaults = None
        no_ctx = user_input.get(CONF_CONTEXT) is None

        if user_input is not None:
            defaults = user_input

            # Check if new config entry matches any existing config entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    if no_ctx:
                        errors[CONF_HOST] = "host_exists"
                        break

                    return self.async_abort(reason="host_exists")

                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    if no_ctx:
                        errors[CONF_NAME] = "name_exists"
                        break

                    return self.async_abort(reason="name_exists")

            if not errors:
                try:
                    # Ensure schema passes custom validation, otherwise catch exception and add error
                    validate_auth(user_input)

                    # Ensure config is valid for a device
                    if not await self.hass.async_add_executor_job(
                        Vizio.validate_config,
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    ):
                        errors["base"] = "invalid_setup"
                except vol.Invalid:
                    errors["base"] = "tv_needs_token"

            if not errors:
                if user_input.get(CONF_CONTEXT) == "config":
                    return self.async_create_entry(
                        title=f"{user_input[CONF_NAME]} (configuration.yaml)",
                        data=user_input,
                    )

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=vizio_schema(defaults), errors=errors
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""

        # Insert record into dict to indicate data came from config import
        import_config[CONF_CONTEXT] = "import"

        return await self.async_step_user(user_input=import_config)
