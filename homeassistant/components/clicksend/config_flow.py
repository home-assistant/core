"""Configurations Flow for Click Send SMS."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_RECIPIENT, CONF_SENDER, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import BASE_API_URL, DOMAIN, HEADERS

ClickSendSchema = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_RECIPIENT, default=[]): cv.string,
        vol.Optional(CONF_SENDER, default=""): cv.string,
    }
)


async def validate_service(config):
    """Get the ClickSend notification service."""
    if not await _authenticate(config):
        raise ValueError("Invalid Credentials")


async def _authenticate(config):
    """Authenticate with ClickSend."""
    url = f"{BASE_API_URL}/account"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            url, auth=aiohttp.BasicAuth(config[CONF_USERNAME], config[CONF_API_KEY])
        ) as resp:
            received = resp.status == 200
            payload = await resp.json()

            if received:
                active = payload["data"]["active"] == 1
                if active:
                    return True
                return False
            return False


class ClickSendConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Clicksend SMS Custom config flow."""

    data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Clicksend SMS User Config Flow Step Handler."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_service(user_input)
            except ValueError:
                errors["base"] = "auth"

            if not errors:
                # Input is valid, set data.
                self.data = user_input
                # Return the form of the next step.
                return self.async_create_entry(
                    title="SMS From "
                    + self.data[CONF_SENDER]
                    + " To "
                    + self.data[CONF_RECIPIENT],
                    data=self.data,
                )

        return self.async_show_form(
            step_id="user", data_schema=ClickSendSchema, errors=errors
        )
