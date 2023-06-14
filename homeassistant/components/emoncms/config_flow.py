"""Provides the required logic for the config flow."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import Hub

_LOGGER = logging.getLogger(__name__)
"""Used for logging messages to the debug window"""

DATA_SCHEMA = vol.Schema(
    {
        CONF_HOST: str,
        CONF_API_KEY: str,
    }
)
"""The schema used for the configuration flow"""


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    host = str(data[CONF_HOST])
    api_key = str(data[CONF_API_KEY])

    _LOGGER.info("Starting validation of user input for EmonCMS")

    if len(host) < 3 or not host.startswith("http"):
        raise InvalidHost

    hub = Hub(hass, host, api_key)
    _LOGGER.info("Testing connection to EmonCMS")
    result = await hub.test_connection()
    if not result:
        # If there is an error, raise an exception to notify HA that there was a
        # problem. The UI will also show there was a problem
        raise CannotConnect

    # Strip protocol
    title = host.removeprefix("http://").removeprefix("http://")

    return {"title": title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EmonCMS config flow."""

    VERSION = 1
    """
    The schema version of the entries that it creates
    Home Assistant will call your migrate method if the version changes
    """

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    """The connection class of the integration"""

    async def async_step_user(self, user_input=None):
        """Provide the configuration flow."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                # The error string is set here, and should be translated.
                # This example does not currently cover translations, see the
                # comments on `DATA_SCHEMA` for further details.
                # Set the error on the `host` field, not the entire form.
                errors["host"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found
        # with the input.
        _LOGGER.info("Showing EmonCMS config form")
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
