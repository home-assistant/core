"""Handle a config flow for Plexamp Media Player."""

import logging
import xml.etree.ElementTree as ET

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (  # Ensure you have this in your const.py
    CONF_PLEX_IP_ADDRESS,
    CONF_PLEX_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PlexampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plexamp Media Player."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate user input
            host = user_input[CONF_HOST]
            # Example validation: Check if it's an IP address or a domain name (basic validation)
            try:
                (
                    connection_successful,
                    device_name,
                    device_id,
                ) = await self.async_test_connection(self.hass, host)

                if not connection_successful:
                    _LOGGER.error(
                        "Couldn't connect to Plexamp, connection was not successful"
                    )
                    errors["base"] = "invalid_host"

                if not errors:
                    # If validation passes, proceed to create the entry
                    unique_id = device_id
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=device_name, data=user_input)
            except Exception as e:
                _LOGGER.error("Error trying to connect to Plexamp: %s", e)

        # If there's user input that led to errors, or if we're showing the form initially
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PLEX_TOKEN): str,
                    vol.Optional(CONF_PLEX_IP_ADDRESS): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": "Host (IP address or domain name)"},
        )

    async def async_test_connection(
        self, hass: HomeAssistant, host: str
    ) -> (bool, str, str):
        """Return True if connection to the provided host is successful."""

        url = f"http://{host}:32500/resources"
        session = async_get_clientsession(hass)

        _LOGGER.debug("URL: %s", url)
        _LOGGER.debug("User session: %s", session)

        try:
            async with session.get(url) as response:
                text = await response.text()
                root = ET.fromstring(text)

                timeline = root.find("Player")

                _LOGGER.debug("Settings response: %s", timeline)
                device_name = timeline.get("title", "Plexamp")
                device_id = timeline.get("f1f80951-4820-46ec-942c-6492a40419c3", url)

                _LOGGER.debug(
                    "Connection with %s was successful. New media_player found: %s",
                    url,
                    device_name,
                )
                return response.status == 200, device_name, device_id
        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout trying to connect to Plexamp")

        return False, None
