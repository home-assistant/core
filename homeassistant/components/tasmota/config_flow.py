"""Config flow for Tasmota."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.mqtt import valid_subscribe_topic

from .const import (  # pylint:disable=unused-import
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_config()

    async def async_step_config(self, user_input=None):
        """Confirm the setup."""
        errors = {}
        data = {CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX}

        if user_input is not None:
            bad_prefix = False
            if self.show_advanced_options:
                prefix = user_input[CONF_DISCOVERY_PREFIX]
                try:
                    valid_subscribe_topic(f"{prefix}/#")
                except vol.Invalid:
                    errors["base"] = "invalid_discovery_topic"
                    bad_prefix = True
                else:
                    data = user_input
            if not bad_prefix:
                return self.async_create_entry(title="Tasmota", data=data)

        fields = {}
        if self.show_advanced_options:
            fields[vol.Optional(CONF_DISCOVERY_PREFIX, default=DEFAULT_PREFIX)] = str

        return self.async_show_form(
            step_id="config", data_schema=vol.Schema(fields), errors=errors
        )
