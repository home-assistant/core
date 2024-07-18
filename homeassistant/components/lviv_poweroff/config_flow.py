"""Config flow for Lviv Power Offline integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, POWEROFF_GROUP_CONF, PowerOffGroup
from .energyua_scrapper import EnergyUaScrapper

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(POWEROFF_GROUP_CONF): vol.Coerce(PowerOffGroup),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    scrapper = EnergyUaScrapper(data[POWEROFF_GROUP_CONF])

    if not await scrapper.validate():
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        "title": "Lviv Power Offline",
        POWEROFF_GROUP_CONF: data[POWEROFF_GROUP_CONF],
    }


class LvivPowerOffConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lviv Power Offline."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
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
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
