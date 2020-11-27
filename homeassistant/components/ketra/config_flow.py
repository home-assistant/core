import logging

import aiohttp
from aioketraapi.oauth import OAuthTokenResponse
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({("host"): str})

_LOGGER = logging.getLogger(__name__)


class KetraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ketra config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the ketra config flow."""
        self.account_credentials = None
        self.oauth_token = None
        self.installations = None

    async def async_step_user(self, user_input=None):
        errors = {}
        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_CLIENT_ID): str,
            vol.Required(CONF_CLIENT_SECRET): str,
        }

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        if self.account_credentials is None:
            self.account_credentials = user_input
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            oauth_response = await OAuthTokenResponse.request_token(
                client_id, client_secret, username, password
            )
            if oauth_response is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(data_schema),
                    errors={CONF_PASSWORD: "login"},
                )

            self.oauth_token = oauth_response.access_token
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://my.goketra.com/api/v4/locations.json?access_token={self.oauth_token}"
                ) as response:
                    if response.status == 200:
                        api_resp = await response.json()
                        self.installations = api_resp['content']
                        inst_map = {
                            inst["id"]: inst["title"] for inst in self.installations
                        }
                        data_schema = {
                            vol.Required("installation_ids"): cv.multi_select(inst_map)
                        }
                        return self.async_show_form(
                            step_id="user", data_schema=vol.Schema(data_schema)
                        )
                    else:
                        return self.async_show_form(
                            step_id="user",
                            data_schema=vol.Schema(data_schema),
                            errors={"installation_ids": "connection"},
                        )

        assert "installation_ids" in user_input
        config_data = {
            CONF_ACCESS_TOKEN: self.oauth_token,
            "installation_ids": user_input["installation_ids"],
        }
        return self.async_create_entry(title="ketra config", data=config_data)
