"""Config flow for Elro Connects integration."""
from __future__ import annotations

import logging
from typing import Any

from elro.api import K1
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ELRO_CONNECTS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("connector_id"): str,
        vol.Optional("port", default=1025): int,
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
