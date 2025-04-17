"""Config flow for the portainer integration."""

from __future__ import annotations

import logging
from typing import Any

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=CONF_DEFAULT_PORT): int,
        vol.Required(CONF_API_KEY): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    api_url = f"{data[CONF_HOST]}:{data[CONF_PORT]}"

    client = Portainer(
        api_url=api_url,
        api_key=data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    try:
        endpoints = await client.get_endpoints()
    except PortainerAuthenticationError:
        raise InvalidAuth from None
    except PortainerConnectionError as err:
        raise CannotConnect from err
    except PortainerTimeoutError as err:
        raise PortainerTimeout from err

    _LOGGER.debug("Connected to Portainer API: %s", api_url)

    portainer_data: list[dict[str, Any]] = []

    for endpoint in endpoints:
        assert endpoint.id
        containers = await client.get_containers(endpoint.id)
        _LOGGER.debug(
            "Found %d containers on endpoint %s", len(containers), endpoint.name
        )
        portainer_data.append(
            {
                "id": endpoint.id,
                "name": endpoint.name,
                "containers": containers,
            }
        )

    return {
        "title": api_url,
        "portainer": portainer_data,
    }


class PortainerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Portainer."""


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except PortainerTimeout:
                errors["base"] = "timeout_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(api["title"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=api["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class PortainerTimeout(HomeAssistantError):
    """Error to indicate a timeout occurred."""
