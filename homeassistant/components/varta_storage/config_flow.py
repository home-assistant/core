"""Config flow for VARTA Storage integration."""
from __future__ import annotations

from typing import Any

from vartastorage import vartastorage
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import _LOGGER, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_PORT, default=502): int}
)


class VartaHub:
    """Provide methods for GUI configuration."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.serial = ""

    def test_connection(self) -> bool:
        """Tests a connection to the VartaStorage device."""
        varta = vartastorage.VartaStorage(self.host, self.port)
        try:
            varta.get_serial()
            self.serial = varta.serial
            return bool(varta.client.connect())
        except ValueError:
            return False

    def get_serial(self):
        """Collect serial number of the VartaStorage device."""
        varta = vartastorage.VartaStorage(self.host, self.port)
        try:
            varta.get_serial()
            return varta.serial
        except ValueError:
            return False


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = VartaHub(data["host"], data["port"])

    # Used PyPI package is not built with async, passing to the sync executor.
    if not await hass.async_add_executor_job(hub.test_connection):
        raise CannotConnect

    # Return info stored in the config entry.
    return {"title": data["host"] + " (S/N: " + hub.serial + ")", "serial": hub.serial}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VARTA Storage."""

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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["serial"])
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
