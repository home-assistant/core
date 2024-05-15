"""Config flow for the SolarEdge platform."""

from __future__ import annotations

import socket
from typing import Any

from aiohttp import ClientError
import aiosolaredge
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import CONF_SITE_ID, DEFAULT_NAME, DOMAIN


class SolarEdgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    @callback
    def _async_current_site_ids(self) -> set[str]:
        """Return the site_ids for the domain."""
        return {
            entry.data[CONF_SITE_ID]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_SITE_ID in entry.data
        }

    def _site_in_configuration_exists(self, site_id: str) -> bool:
        """Return True if site_id exists in configuration."""
        return site_id in self._async_current_site_ids()

    async def _async_check_site(self, site_id: str, api_key: str) -> bool:
        """Check if we can connect to the soleredge api service."""
        session = async_get_clientsession(self.hass)
        api = aiosolaredge.SolarEdge(api_key, session)
        try:
            response = await api.get_details(site_id)
            if response["details"]["status"].lower() != "active":
                self._errors[CONF_SITE_ID] = "site_not_active"
                return False
        except (TimeoutError, ClientError, socket.gaierror):
            self._errors[CONF_SITE_ID] = "could_not_connect"
            return False
        except KeyError:
            self._errors[CONF_SITE_ID] = "invalid_api_key"
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            if self._site_in_configuration_exists(user_input[CONF_SITE_ID]):
                self._errors[CONF_SITE_ID] = "already_configured"
            else:
                site = user_input[CONF_SITE_ID]
                api = user_input[CONF_API_KEY]
                can_connect = await self._async_check_site(site, api)
                if can_connect:
                    return self.async_create_entry(
                        title=name, data={CONF_SITE_ID: site, CONF_API_KEY: api}
                    )

        else:
            user_input = {CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: "", CONF_API_KEY: ""}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(CONF_SITE_ID, default=user_input[CONF_SITE_ID]): str,
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                }
            ),
            errors=self._errors,
        )
