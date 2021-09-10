"""Config flow for PoolSense integration."""
import logging

from poolsense import PoolSense
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PoolSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PoolSense."""

    VERSION = 1

    def __init__(self):
        """Initialize PoolSense config flow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:

            _LOGGER.debug(
                "Configuring user: %s - Password hidden", user_input[CONF_EMAIL]
            )

            poolsense = PoolSense(
                aiohttp_client.async_get_clientsession(self.hass),
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                False,
            )
            api_key_valid = await poolsense.test_poolsense_credentials()

            if not api_key_valid:
                errors["base"] = "invalid_auth"

            if not errors:

                if not user_input[CONF_DEVICE_ID]:
                    await self.async_set_unique_id(api_key_valid)
                else:
                    await self.async_set_unique_id(user_input[CONF_DEVICE_ID])

                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self.unique_id,
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_DEVICE_ID: self.unique_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_DEVICE_ID, default=""): str,
                }
            ),
            errors=errors,
        )
