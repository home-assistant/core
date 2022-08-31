"""Config flow for ecowitt."""
from __future__ import annotations

import logging
import secrets
from typing import Any

from aioecowitt import EcoWittListener
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_PATH, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PATH, default=f"/{secrets.token_urlsafe(16)}"): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_PORT] == data[CONF_PORT]:
            raise InvalidPort

    # Check if the port is in use
    try:
        listener = EcoWittListener(port=data[CONF_PORT])
        await listener.start()
        await listener.stop()
    except OSError:
        raise InvalidPort from None

    return {"title": f"Ecowitt on port {data[CONF_PORT]}"}


class EcowittConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Ecowitt."""

    VERSION = 1

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
        except InvalidPort:
            errors["base"] = "invalid_port"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidPort(HomeAssistantError):
    """Error to indicate there port is not usable."""
