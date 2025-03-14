"""Config flow for Flexit Nordic (BACnet) integration."""

from __future__ import annotations

import asyncio.exceptions
import logging
from typing import Any

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_ID = 2

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): int,
    }
)


class FlexitBacnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flexit Nordic (BACnet)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = FlexitBACnet(
                user_input[CONF_IP_ADDRESS], user_input[CONF_DEVICE_ID]
            )
            try:
                await device.update()
            except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device.device_name, data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
