"""Config flow for PoolSense integration."""
import logging

from poolsense import PoolSense
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class PoolSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PoolSense."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize PoolSense config flow."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            _LOGGER.debug(
                "Configuring user: %s - Password hidden", user_input[CONF_EMAIL]
            )

            poolsense = PoolSense(
                aiohttp_client.async_get_clientsession(self.hass),
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            api_key_valid = await poolsense.test_poolsense_credentials()

            if not api_key_valid:
                self._errors["base"] = "invalid_auth"

            if not self._errors:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=self._errors or {},
        )
