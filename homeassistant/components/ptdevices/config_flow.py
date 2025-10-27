"""Config flow for PTDevices integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
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

_CONF_SCHEMA = vol.Schema(
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

    body: dict[str, Any] = response.get("body", {})

    device_title: str = body.get("title", "")
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

        # Show user form when no input provided
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_CONF_SCHEMA)

        # Make sure the device isn't already configured
        self._async_abort_entries_match({CONF_DEVICE_ID: user_input[CONF_DEVICE_ID]})

        # Test the connection
        errors: dict[str, str] = {}
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
            # Connection Successful
            return self.async_create_entry(title=device_title, data=user_input)

        # Connection Unsuccessful, show errors
        return self.async_show_form(
            step_id="user", data_schema=_CONF_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        reauth_entry = self._get_reauth_entry()
        reauth_data = {**reauth_entry.data}

        # Show the user input form
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_TOKEN): str,
                    }
                ),
            )

        reauth_data.update(user_input)

        # Test connection to server
        errors: dict[str, str] = {}
        try:
            await validate_input(self.hass, reauth_data)
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
            # Connection Successful
            return self.async_update_reload_and_abort(reauth_entry, data=reauth_data)

        # Error occurred, Show form again
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MalformedResponse(HomeAssistantError):
    """Error to indicate the response was malformed."""
