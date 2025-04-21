"""Config flow for the portainer integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import CookieJar
from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    url = URL(data[CONF_URL]).human_repr()
    session = async_create_clientsession(
        hass,
        data[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    client = Portainer(
        api_url=url,
        api_key=data[CONF_API_KEY],
        session=session,
    )

    try:
        endpoints = await client.get_endpoints()
    except PortainerAuthenticationError:
        raise InvalidAuth from None
    except PortainerConnectionError as err:
        raise CannotConnect from err
    except PortainerTimeoutError as err:
        raise PortainerTimeout from err

    _LOGGER.debug("Connected to Portainer API: %s", url)

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
        "title": url,
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
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

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
                _LOGGER.debug("Erwin title: %s", api["title"])
                return self.async_create_entry(title=api["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class PortainerTimeout(HomeAssistantError):
    """Error to indicate a timeout occurred."""
