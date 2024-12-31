"""Config flow for the Model Context Protocol integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import mcp_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.url,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and connect to the MCP server."""
    url = data[CONF_URL]
    try:
        async with mcp_client(url) as session:
            response = await session.initialize()
    except httpx.TimeoutException as error:
        raise TimeoutConnectError from error
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            raise InvalidAuth from error
        raise ServerError from error
    except httpx.HTTPError as error:
        raise CannotConnect from error

    if not response.capabilities.tools:
        raise MissingCapabilities(
            f"MCP Server {url} does not support 'Tools' capability"
        )

    return {"title": response.serverInfo.name}


class ModelContextProtocolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except TimeoutConnectError:
                errors["base"] = "timeout_connect"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ServerError:
                errors["base"] = "server_error"
            except MissingCapabilities:
                errors["base"] = "missing_capabilities"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class TimeoutConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class ServerError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MissingCapabilities(HomeAssistantError):
    """Error to indicate that the MCP server is missing required capabilities."""
