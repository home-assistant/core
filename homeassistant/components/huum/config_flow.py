"""Config flow for huum integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from huum.huum import Huum
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for huum."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                huum_handler = Huum(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                )
                await huum_handler.status()
            except aiohttp.ClientError:
                _LOGGER.error("Could not log in to Huum with given credentials")
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
