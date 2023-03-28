"""Config flow for Solvis Remote integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # hub = await hass.async_add_executor_job(SC2XMLReaderValidator, data[CONF_HOST])

    # result = await hass.async_add_executor_job(hub.validate_host())
    # if not result:
    #    raise CannotConnect

    # if not await hub.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD]):
    #    raise InvalidAuth

    # if not await hub.validate_uri(data[CONF_USERNAME], data[CONF_PASSWORD]):
    #    raise CannotConnect

    the_title = "Solvis Remote"

    # try:
    #    the_device = await hass.async_add_executor_job(
    #        SC2XMLReader, hub.url, data[CONF_USERNAME], data[CONF_PASSWORD]
    #    )
    #    the_model = the_device.getModel()
    # except:
    #    raise CannotConnect

    return {"title": the_title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solvis Heating."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
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


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
