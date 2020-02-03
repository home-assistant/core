"""Config flow for Ziggo Next integration."""
from collections import OrderedDict
import logging

import voluptuous as vol
from ziggonext import ZiggoNext, ZiggoNextAuthenticationError, ZiggoNextConnectionError

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_COUNTRY_CODE, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ziggo Next."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            api = ZiggoNext(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY_CODE],
            )
            try:
                api.initialize(_LOGGER)
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            except ZiggoNextConnectionError:
                errors["base"] = "cannot_connect"
            except ZiggoNextAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        countries = ["nl", "ch"]
        fields = OrderedDict()
        fields[vol.Required(CONF_USERNAME)] = str
        fields[vol.Required(CONF_PASSWORD)] = str
        fields[vol.Optional(CONF_COUNTRY_CODE, default="nl")] = vol.In(list(countries))

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )
