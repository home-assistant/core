"""Config flow for PTDevices integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aioptdevices
from aioptdevices.interface import PTDevicesResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .device import ptdevices_get_data

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    # Test Connection
    try:
        async with asyncio.timeout(10):
            response: PTDevicesResponse = await ptdevices_get_data(
                hass, data[CONF_API_TOKEN], data[CONF_DEVICE_ID]
            )

    # Catch any errors
    except aioptdevices.PTDevicesRequestError as err:
        raise CannotConnect from err

    except aioptdevices.PTDevicesUnauthorizedError as err:
        raise InvalidAuth from err

    except aioptdevices.PTDevicesForbiddenError as err:
        raise InvalidAuth from err

    device_title: str = response.get("body", {}).get("title", "")

    if device_title == "":
        raise MalformedResponse("Device title was not included in the response.")

    # Return info that you want to store in the config entry.
    return device_title


class PTDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PTDevices."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_title: str = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MalformedResponse:
                errors["base"] = "malformed_response"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=device_title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MalformedResponse(HomeAssistantError):
    """Error to indicate the response was malformed."""
