"""Config flow for SpaNET integration."""
from __future__ import annotations

import logging

import spanetlib
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class SpanetConfigFlow(config_entries.ConfigFlow):
    """SpaNET auth."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            userData = await spanetlib.login(username=username, password=password)

            if userData["success"] is True:
                return self.async_create_entry(
                    title=userData["spa_name"],
                    data={
                        "access_token": userData["access_token"],
                        "refresh_token": userData["refresh_token"],
                        "spa_name": userData["spa_name"],
                    },
                )

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
                errors={"base": "Invalid email or password. Please try again."},
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
