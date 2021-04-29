"""Config flow for Omnilogic integration."""
import logging

from omnilogic import LoginException, OmniLogic, OmniLogicException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_SCAN_INTERVAL, DEFAULT_PH_OFFSET, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Omnilogic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        config_entry = self.hass.config_entries.async_entries(DOMAIN)
        if config_entry:
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = aiohttp_client.async_get_clientsession(self.hass)
            omni = OmniLogic(username, password, session)

            try:
                await omni.connect()
            except LoginException:
                errors["base"] = "invalid_auth"
            except OmniLogicException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input["username"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Omnilogic", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Omnilogic client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        "ph_offset",
                        default=self.config_entry.options.get(
                            "ph_offset", DEFAULT_PH_OFFSET
                        ),
                    ): vol.All(vol.Coerce(float)),
                }
            ),
        )
