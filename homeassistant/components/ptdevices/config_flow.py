"""Config flow for PTDevices integration."""

from __future__ import annotations

import logging
from typing import Any

import aioptdevices
from aioptdevices.configuration import Configuration
from aioptdevices.interface import Interface
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> tuple[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    session = async_get_clientsession(hass)
    ptdevices_interface = Interface(
        Configuration(
            auth_token=data[CONF_API_TOKEN],
            device_id="*",  # Retrieve data for all devices in account
            url=DEFAULT_URL,
            session=session,
        )
    )

    # Test Connection
    try:
        response = await ptdevices_interface.get_data()
    except aioptdevices.PTDevicesRequestError as err:
        raise CannotConnect from err

    except aioptdevices.PTDevicesUnauthorizedError as err:
        raise InvalidAuth from err

    body = response["body"]

    # Ensure the first device exists
    first_device = next(iter(body.values()), None)
    if first_device is None:
        raise NoDevicesFound

    # Ensure the user_name and user_id exist
    user_name = first_device.get("user_name")
    user_id = first_device.get("user_id")
    if user_name is None or user_id is None:
        raise MalformedResponse

    title: str = str(user_name)
    unique_id: str = str(user_id)

    # Return title to be used for hub name
    return (title, unique_id)


class PTDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PTDevices."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        # Test connection when user data is available
        if user_input is not None:
            # Make sure the device isn't already configured
            self._async_abort_entries_match(
                {CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
            )

            # Test connection
            try:
                title, unique_id = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_access_token"
            except NoDevicesFound:
                errors["base"] = "no_devices_found"
            except MalformedResponse:
                errors["base"] = "malformed_response"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Connection Successful
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        # Show setup form
        return self.async_show_form(
            step_id="user", data_schema=_CONF_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoDevicesFound(HomeAssistantError):
    """No devices were found in the account."""


class MalformedResponse(HomeAssistantError):
    """Error indicating the response from the library is missing something required by the home assistant integration."""
