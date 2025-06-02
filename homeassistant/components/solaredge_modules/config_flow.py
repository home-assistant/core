"""Config flow for the SolarEdge Modules integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from solaredge_web import SolarEdgeWeb
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CONF_SITE_ID = "site_id"
DEFAULT_NAME = "SolarEdge"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SITE_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = SolarEdgeWeb(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        site_id=data[CONF_SITE_ID],
        session=aiohttp_client.async_get_clientsession(hass),
    )
    try:
        await api.async_get_equipment()
    except aiohttp.ClientResponseError as err:
        if err.status == 401:
            _LOGGER.error("Invalid credentials")
            raise InvalidAuth from err
        if err.status == 403:
            _LOGGER.error("Invalid credentials for site ID: %s", data[CONF_SITE_ID])
            raise InvalidAuth from err
        if err.status == 400:
            _LOGGER.error("Invalid site ID: %s", data[CONF_SITE_ID])
            raise CannotConnect from err
        raise CannotConnect from err
    except aiohttp.ClientError as err:
        raise CannotConnect from err


class SolarEdgeOptimizersConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolarEdge Modules."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SITE_ID])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_SITE_ID: user_input[CONF_SITE_ID],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
