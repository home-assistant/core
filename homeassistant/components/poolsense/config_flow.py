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

    _options = None

    def __init__(self):
        """Initialize PoolSense config flow."""
        self._email = None
        self._password = None
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            _LOGGER.debug("Configuring user: %s - Password hidden.", self._email)

            poolsense = PoolSense()
            api_key_valid = await poolsense.test_poolsense_credentials(
                aiohttp_client.async_get_clientsession(self.hass),
                self._email,
                self._password,
            )

            if not api_key_valid:
                self._errors["base"] = "auth"

            if not self._errors:
                return self.async_create_entry(
                    title=self._email,
                    data={CONF_EMAIL: self._email, CONF_PASSWORD: self._password},
                )

        return await self._show_setup_form(user_input, self._errors)

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors or {},
        )
