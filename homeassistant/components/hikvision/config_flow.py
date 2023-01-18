"""Config flow for Hikvision integration."""
from __future__ import annotations

import logging
from typing import Any

from pyhik.hikvision import HikCamera
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self) -> None:
        """Initialize."""

    async def authenticate(self, hass: HomeAssistant, data: dict[str, Any]) -> bool:
        """Test if we can authenticate with the host."""
        protocol = "https" if data[CONF_SSL] else "http"
        host = data[CONF_HOST]
        url = f"{protocol}://{host}"
        port = data[CONF_PORT]
        username = data[CONF_USERNAME]
        password = data[CONF_PASSWORD]

        hikdata = await hass.async_add_executor_job(
            HikCamera, url, port, username, password
        )
        return hikdata.name is not None


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    hub = PlaceholderHub()

    if not await hub.authenticate(hass, data):
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision."""

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

    async def async_step_import(self, user_input):
        """Handle import."""
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2023.4.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
