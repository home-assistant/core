"""Config flow for Leslie's Pool Water Tests integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import LesliesPoolApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required("water_test_url"): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=300): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    url = data["water_test_url"]
    match = re.search(r"poolProfileId=(\d+)&poolName=([^&]+)", url)
    if not match:
        raise InvalidURL from None

    pool_profile_id = match.group(1)
    pool_name = match.group(2)

    api = LesliesPoolApi(
        data[CONF_USERNAME], data[CONF_PASSWORD], pool_profile_id, pool_name
    )

    # Run the authenticate method in the executor to avoid blocking the event loop
    try:
        authenticated = await hass.async_add_executor_job(api.authenticate)
    except CannotConnect as err:
        raise CannotConnect from err
    except InvalidAuth as err:
        raise InvalidAuth from err

    if not authenticated:
        raise InvalidAuth

    return {
        "title": "Leslie's Pool",
        "username": data[CONF_USERNAME],
        "password": data[CONF_PASSWORD],
        "pool_profile_id": pool_profile_id,
        "pool_name": pool_name,
        "scan_interval": data[CONF_SCAN_INTERVAL],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Leslie's Pool Water Tests."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidURL:
                errors["base"] = "invalid_url"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=info)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class InvalidURL(HomeAssistantError):
    """Error to indicate the provided URL is invalid."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
