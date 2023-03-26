"""Config flow for Flexit Nordic (BACnet) integration."""
from __future__ import annotations

import asyncio.exceptions
import logging
from typing import Any

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_ID = 2

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): int,
    }
)


async def validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    device = FlexitBACnet(data[CONF_IP_ADDRESS], data[CONF_DEVICE_ID])

    try:
        await device.update()
    except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
        raise CannotConnect from exc

    # Return info that you want to store in the config entry.
    return device.serial_number


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flexit Nordic (BACnet)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
