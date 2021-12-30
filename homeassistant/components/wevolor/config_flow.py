"""Config flow for Wevolor Control for Levolor Motorized Blinds integration."""
from __future__ import annotations

import logging
from typing import Any

from pywevolor import Wevolor
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONFIG_CHANNELS, CONFIG_HOST, CONFIG_TILT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_HOST): str,
        vol.Required(CONFIG_TILT, default=False): bool,
        vol.Required(CONFIG_CHANNELS, default=6): vol.All(int, vol.Range(min=1, max=6)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    wevolor = Wevolor(data[CONFIG_HOST])
    status = await hass.async_add_executor_job(wevolor.get_status)

    if not status:
        raise CannotConnect

    return await status


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wevolor Control for Levolor Motorized Blinds."""

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
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.exception(f"Unexpected exception: {e}")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["remote"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
