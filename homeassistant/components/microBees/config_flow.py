"""Config Flow for microBees."""
from __future__ import annotations

import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
)

from .const import CONFIG_ENTRY_VERSION

import json
import aiohttp
import base64

_LOGGER = logging.getLogger(__name__)


class microBeesFlowHandler(config_entries.ConfigFlow, domain=CONF_DOMAIN):
    """Handle a microBees config flow."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}

        # Login to microBees with user data.
        if user_input is not None:
            self.data.update(user_input)
            async with aiohttp.ClientSession() as session:
                userpass = (
                    self.data[CONF_CLIENT_ID] + ":" + self.data[CONF_CLIENT_SECRET]
                )
                auth = base64.b64encode(userpass.encode()).decode()

                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Basic %s" % auth,
                }

                body = {
                    "username": self.data[CONF_USERNAME],
                    "password": self.data[CONF_PASSWORD],
                    "scope": "read write",
                    "grant_type": "password",
                }

                async with session.post(
                    "https://dev.microbees.com/oauth/token", headers=headers, data=body
                ) as resp:
                    if resp.ok:
                        data = await resp.text()
                        js = json.loads(data)
                        self.data[CONF_TOKEN] = js.get("access_token")
                    else:
                        errors["base"] = "invalid_token2"

                    if not errors:
                        return self.async_create_entry(
                            title=self.data[CONF_USERNAME], data=self.data
                        )

        # Show User Input form.
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }
        )
        return self.async_show_form(
            description_placeholders={CONF_USERNAME: "Username"},
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
