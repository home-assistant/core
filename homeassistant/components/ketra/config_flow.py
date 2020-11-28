"""Config flow to configure Ketra-based lighting products."""

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
        self.installation_id_to_title_dict = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_CLIENT_ID): str,
            vol.Required(CONF_CLIENT_SECRET): str,
        }

        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=vol.Schema(data_schema)
            )

        self.account_credentials = user_input
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        client_id = user_input[CONF_CLIENT_ID]
        client_secret = user_input[CONF_CLIENT_SECRET]

        oauth_response = await OAuthTokenResponse.request_token(
            client_id, client_secret, username, password
        )
        if oauth_response is None:
            # login error
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(data_schema),
                errors={CONF_PASSWORD: "login"},
            )

        self.oauth_token = oauth_response.access_token
        inst_dict = await self._get_installations()
        if inst_dict is None:
            # connection error to one of the my.goketra.com endpoints
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(data_schema),
                errors={"installation_id": "connection"},
                description_placeholders={},
            )

        current_entries = self._async_current_entries() or []
        for entry in current_entries:
            if entry.data["installation_id"] in inst_dict:
                inst_dict.pop(entry.data["installation_id"])

        if len(inst_dict) == 0:
            return self.async_abort(reason="no_installations")

        self.installation_id_to_title_dict = inst_dict
        return await self.async_step_select_installation()

    async def async_step_select_installation(self, user_input=None):
        """Handle installation selection."""

        if user_input is None:
            _LOGGER.warning("showing select installation form")
            data_schema = {
                vol.Required("installation_id"): vol.In(
                    {**self.installation_id_to_title_dict}
                )
            }
            return self.async_show_form(
                step_id="select_installation", data_schema=vol.Schema(data_schema)
            )

        assert "installation_id" in user_input
        installation_name = self.installation_id_to_title_dict[
            user_input["installation_id"]
        ]
        config_data = {
            CONF_ACCESS_TOKEN: self.oauth_token,
            "installation_id": user_input["installation_id"],
            "installation_name": installation_name,
        }
        return self.async_create_entry(title=installation_name, data=config_data)

    async def _get_installations(self):
        async with aiohttp.ClientSession() as session:
            # first, get all installations to which the user has access.
            async with session.get(
                f"https://my.goketra.com/api/v4/locations.json?access_token={self.oauth_token}"
            ) as response:
                if response.status == 200:
                    api_resp = await response.json()
                    installations = api_resp["content"]
                    # next, filter out all installations that don't correspond to a discovered hub
                    async with session.get(
                        "https://my.goketra.com/api/n4/v1/query"
                    ) as response:
                        if response.status == 200:
                            api_resp = await response.json()
                            local_installation_ids = [
                                inst["installation_id"] for inst in api_resp["content"]
                            ]
                            return {
                                inst["id"]: inst["title"]
                                for inst in installations
                                if inst["id"] in local_installation_ids
                            }
                        else:
                            _LOGGER.warning(
                                f"Received status code {response.status} when querying for hubs"
                            )
                else:
                    _LOGGER.warning(
                        f"Received status code {response.status} when querying for accessible installations"
                    )
        return None
