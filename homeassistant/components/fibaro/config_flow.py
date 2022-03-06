"""Config flow for Fibaro integration."""
from __future__ import annotations

import logging
from typing import Any

from fiblary3.common.exceptions import HTTPException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from . import FibaroController
from .const import CONF_IMPORT_PLUGINS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_IMPORT_PLUGINS, default=False): bool,
    }
)


def _connect_to_fibaro(data: dict[str, Any]) -> tuple[bool, FibaroController]:
    """Validate the user input allows us to connect to fibaro."""
    controller = FibaroController(data)
    connected = controller.connect()
    if connected:
        _LOGGER.debug(
            "Successful connection to fibaro home center with url %s", data[CONF_URL]
        )

    return connected, controller


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    connected, controller = await hass.async_add_executor_job(_connect_to_fibaro, data)
    if not connected:
        raise CannotConnect

    _LOGGER.debug(
        "Successfully connected to fibaro home center %s with name %s",
        controller.hub_serial,
        controller.name,
    )
    return {"serial_number": controller.hub_serial, "name": controller.name}


class FibaroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fibaro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HTTPException as http_ex:
                if http_ex.details == "Forbidden":
                    errors["base"] = "invalid_auth"
                else:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: ConfigType | None) -> FlowResult:
        """Import a config entry."""
        return await self.async_step_user(import_config)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
