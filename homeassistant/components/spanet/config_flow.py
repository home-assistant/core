"""Config flow for SpaNET integration."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class SpanetConfigFlow(config_entries.ConfigFlow):
    """SpaNET auth."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            payload = {
                "email": username,
                "password": password,
                "userDeviceId": "h53pr40n3tHomeAssistant",
                "language": "eng",
            }
            url = LOGIN
            try:
                async with aiohttp.ClientSession() as session, session.post(
                    url, json=payload
                ) as response:
                    if response.status == 200:
                        # Authentication successful
                        userData = await response.json()
                        return self.async_create_entry(
                            title=userData["spa_name"],
                            data={
                                "access_token": userData["access_token"],
                                "refresh_token": userData["refresh_token"],
                                "spa_name": userData["spa_name"],
                            },
                        )

                    # Authentication failed
                    _LOGGER.error(
                        "Authentication failed with status code: %s",
                        response.status,
                    )
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("username"): str,
                            vol.Required("password"): str,
                        },
                        errors={"base": "Error. Please try again."},
                    ),
                )

            except aiohttp.ClientError as err:
                _LOGGER.error("Error occurred during API call: %s", err)
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("username"): str,
                            vol.Required("password"): str,
                        },
                        errors={"base": "Error. Please try again."},
                    ),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
        )
