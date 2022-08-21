"""Config flow for air-Q integration.

Off all integration components, the content of this file is being executed first
when the user sets up the integration.
"""
from __future__ import annotations

import logging
from typing import Any

from aioairq import AirQ
from aiohttp.client_exceptions import ClientConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        auth_success = await AirQ(
            data[CONF_IP_ADDRESS], data[CONF_PASSWORD]
        ).test_authentication()
    except ClientConnectionError as exc:
        raise CannotConnect from exc

    if not auth_success:
        raise InvalidAuth


async def fetch_device_info(data: dict[str, Any]) -> tuple[str, str]:
    """Fetch device information: name and a unique ID."""
    airq = AirQ(data[CONF_IP_ADDRESS], data[CONF_PASSWORD])
    config = await airq.get("config")
    device_id: str = config["id"]
    device_name: str = config["devicename"]
    return device_name, device_id


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for air-Q."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step: authentication.

        This prompts the user to enter the credentials to access the device.
        It then tries to connect to the device, and to assess the validity
        of the password.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(user_input)
        except CannotConnect:
            _LOGGER.debug(
                "Failed to connect to device %s. Check the specified IP address / mDNS, "
                "as well as whether the device is connected to power and the WiFi",
                user_input[CONF_IP_ADDRESS],
            )
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            _LOGGER.error(
                "Incorrect password for device %s", user_input[CONF_IP_ADDRESS]
            )
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            # This really shouldn't happen, so .exception is perhaps more appropriate
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug("Successfully connected to %s", user_input[CONF_IP_ADDRESS])

            device_name, device_id = await fetch_device_info(user_input)
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=device_name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
