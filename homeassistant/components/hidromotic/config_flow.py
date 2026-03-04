"""Config flow for Hidromotic integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhidromotic import HidromoticClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, INITIAL_DATA_WAIT_SECONDS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = HidromoticClient(data[CONF_HOST])

    try:
        if not await client.connect():
            raise CannotConnect

        # Wait for initial data from device
        await asyncio.sleep(INITIAL_DATA_WAIT_SECONDS)

        # Get device info
        device_id = client.data.get("pic_id", "unknown")
        is_mini = client.data.get("is_mini", False)
        name = "CHI Smart Mini" if is_mini else "CHI Smart"

    finally:
        await client.disconnect()

    return {"title": f"{name} ({data[CONF_HOST]})", "device_id": device_id}


class HidromoticConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hidromotic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
