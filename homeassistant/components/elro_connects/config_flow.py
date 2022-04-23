"""Config flow for Elro Connects integration."""
from __future__ import annotations

import logging
from typing import Any

from elro.api import K1
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CONNECTOR_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ELRO_CONNECTS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_CONNECTOR_ID): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_INTERVAL): cv.positive_int,
    }
)


class K1ConnectionTest:
    """Elro Connects K1 connection test."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, connector_id: str, port: int) -> bool:
        """Test if we can authenticate with the host."""
        connector = K1(self.host, connector_id, port)
        try:
            await connector.async_connect()
        except K1.K1ConnectionError:
            return False
        finally:
            await connector.async_disconnect()
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    hub = K1ConnectionTest(data["host"])

    if not await hub.authenticate(data["connector_id"], data["port"]):
        raise CannotConnect

    return {"title": "Elro Connects K1 Connector"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elro Connects."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=ELRO_CONNECTS_DATA_SCHEMA
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
            step_id="user", data_schema=ELRO_CONNECTS_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
