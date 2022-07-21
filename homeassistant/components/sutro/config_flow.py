"""Config flow for Sutro integration."""
from __future__ import annotations

import logging
import time
from typing import Any

import jwt
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class SutroHub:
    """Sutro API."""

    def __init__(self, hass: HomeAssistant, api_token: str) -> None:
        """Initialize."""
        self.hass = hass
        self.api_token = api_token

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        payload = jwt.decode(
            self.api_token, "", algorithm="HS512", options={"verify_signature": False}
        )
        if payload["aud"] == "sutro" and payload["exp"] > time.time():
            return True
        return False

    def get_info(self) -> dict[str, Any]:
        """Get info about user and device."""
        query = """
        {
            me {
                id
                firstName
                pool {
                    latestReading {
                        alkalinity
                        chlorine
                        ph
                        readingTime
                    }
                }
            }
        }
        """

        response = requests.post(
            "https://api.mysutro.com/graphql",
            data=query,
            headers={"Authorization": f"Bearer {self.api_token}"},
        )

        return response.json()

    async def async_get_info(self) -> dict[str, Any]:
        """Asynchronously get info about user and device."""
        return await self.hass.async_add_executor_job(self.get_info)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = SutroHub(hass, data["api_token"])

    if not await hub.authenticate():
        raise InvalidAuth

    info = await hub.async_get_info()
    if not info:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": f"{info['data']['me']['firstName']}'s Pool/Spa"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sutro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
