"""Config flow for FX Luminaire Luxor low voltage controller integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import client_exceptions as aio_exceptions
import luxor
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import CONF_INCLUDE_LUXOR_THEMES, DEFAULT_INCLUDE_LUXOR_THEMES, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({CONF_HOST: str})


async def validate_luxor(host: str, hass: HomeAssistant):
    """Validate the host is a Luxor controller.

    Also serves as a mock point for unit testing of forms.
    """
    client = luxor.Client(host, aiohttp_client.async_get_clientsession(hass))

    try:
        await client.get_groups()
    except aio_exceptions.ClientConnectorError as err:
        _LOGGER.warn(err)
        return False
    except aio_exceptions.ClientError as err:
        # in this case we connected with some http server,
        # but to something other than a luxor device
        _LOGGER.warn(f"host: {host} is likely not a Luxor controller. error: {err}")
        return False

    return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    if not await validate_luxor(host, hass):
        raise CannotConnect

    return {"title": "Luxor Controller"}


class LuxorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FX Luminaire Luxor low voltage controller."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LuxorOptionsFlowHandler(config_entry)

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
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class LuxorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Luxor options."""

    def __init__(self, config_entry):
        """Initialize Luxor options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Luxor options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_LUXOR_THEMES,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_LUXOR_THEMES, DEFAULT_INCLUDE_LUXOR_THEMES
                        ),
                    ): bool,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
