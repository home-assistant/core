"""Config flow for Renson Endura Delta integration."""
from __future__ import annotations

import logging
from typing import Any

from rensonVentilationLib.fieldEnum import CO2_FIELD
import rensonVentilationLib.renson as renson
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self, host: str, hass: HomeAssistant) -> None:
        """Initialize."""
        self.host = host
        self.hass = hass

    async def connect(self) -> bool:
        """Test if we can connect with the host."""
        rensonLib = renson.RensonVentilation(self.host)

        try:
            await self.hass.async_add_executor_job(rensonLib.get_data_string, CO2_FIELD)
        except ConnectionError:
            raise CannotConnect
        return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Renson Endura Delta."""

    VERSION = 1

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """
        hub = PlaceholderHub(data["host"], hass)

        if not await hub.connect():
            raise CannotConnect

        return {"title": "Renson Endura Delta"}

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
            info = await self.validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
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
