"""Config flow for the Papouch integration."""

import logging
import re

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .APIClient import PapouchApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

IP_REGEX = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"


class PapouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Papouch."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Tell Home Assistant to use our Options Flow."""
        return PapouchOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step where the user enters the device IP."""
        errors = {}

        if user_input is not None:
            ip_address = user_input["ip_address"]

            if not re.match(IP_REGEX, ip_address):
                errors["ip_address"] = "invalid_ip_address"
            else:
                session = async_get_clientsession(self.hass)
                client = PapouchApiClient(ip_address, session)

                try:
                    await client.fetch_info()
                    return self.async_create_entry(
                        title=f"Papouch {ip_address}", data=user_input
                    )
                except aiohttp.ClientError as err:
                    _LOGGER.error("Failed to connect to the device: %s", err)
                    errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required("ip_address"): str,
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int,
                    vol.Range(min=1, max=3600),  # TODO: hard-coded
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class PapouchOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Papouch."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        # if user_input is not None:
        #     return self.async_create_entry(title="", data=user_input)

        # pass
