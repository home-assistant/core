"""Config Flow for Advantage Air integration."""
from __future__ import annotations

from typing import Any

from hass_splunk import hass_splunk
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

DEFAULT_PORT = 8088
DEFAULT_NAME = "Home Assistant"

SPLUNK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


class SplunkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Advantage Air API connection."""

    VERSION = 1
    DOMAIN = DOMAIN

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get configuration from the user."""
        errors = {}
        if user_input:
            splunk = hass_splunk(
                session=async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                token=user_input[CONF_TOKEN],
                use_ssl=user_input[CONF_SSL],
                verify_ssl=user_input[CONF_VERIFY_SSL],
            )
            if not await splunk.check(connectivity=True, token=False, busy=False):
                errors["base"] = "cannot_connect"
            elif not await splunk.check(connectivity=False, token=True, busy=False):
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SPLUNK_SCHEMA,
            errors=errors,
        )
