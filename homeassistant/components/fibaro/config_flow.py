"""Config flow for Fibaro integration."""
from __future__ import annotations

import logging
from typing import Any

from slugify import slugify
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from . import FibaroAuthFailed, FibaroConnectFailed, FibaroController
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


def _connect_to_fibaro(data: dict[str, Any]) -> FibaroController:
    """Validate the user input allows us to connect to fibaro."""
    controller = FibaroController(data)
    controller.connect_with_error_handling()
    return controller


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    controller = await hass.async_add_executor_job(_connect_to_fibaro, data)

    _LOGGER.debug(
        "Successfully connected to fibaro home center %s with name %s",
        controller.hub_serial,
        controller.hub_name,
    )
    return {
        "serial_number": slugify(controller.hub_serial),
        "name": controller.hub_name,
    }


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
            except FibaroConnectFailed:
                errors["base"] = "cannot_connect"
            except FibaroAuthFailed:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=info["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: ConfigType | None) -> FlowResult:
        """Import a config entry."""
        return await self.async_step_user(import_config)
