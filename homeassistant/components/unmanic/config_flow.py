"""Adds config flow for Unmanic integration."""
import logging

from unmanic_api import Unmanic
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    __version__,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class UnmanicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Unmanic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            await self.async_set_unique_id(
                user_input[CONF_HOST] + str(user_input[CONF_PORT])
            )
            self._abort_if_unique_id_configured()

            connection_valid = await self._test_connection(user_input)
            if not connection_valid:
                self._errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Unmanic (" + user_input[CONF_HOST] + ")", data=user_input
                )

            return await self._show_config_form(user_input)

        user_input = {}
        user_input[CONF_PORT] = DEFAULT_PORT
        user_input[CONF_SSL] = DEFAULT_SSL
        user_input[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL
        user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=user_input[CONF_PORT]): int,
                vol.Optional(CONF_SSL, default=user_input[CONF_SSL]): bool,
                vol.Optional(
                    CONF_VERIFY_SSL, default=user_input[CONF_VERIFY_SSL]
                ): bool,
                vol.Optional(CONF_TIMEOUT, default=user_input[CONF_TIMEOUT]): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=self._errors,
        )

    async def _test_connection(self, user_input):
        """Return true if configuration is valid."""

        try:
            session = async_get_clientsession(self.hass)
            client = Unmanic(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                request_timeout=user_input[CONF_TIMEOUT],
                session=session,
                tls=user_input[CONF_SSL],
                verify_ssl=user_input[CONF_VERIFY_SSL],
                user_agent=f"HomeAssistant/Unmanic/{__version__}",
            )
            await client.get_version()
            return True
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error(exception)
        return False
