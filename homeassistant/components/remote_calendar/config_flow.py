"""Config flow for Local Calendar integration."""

from __future__ import annotations

import logging
from typing import Any

from httpx import ConnectError, HTTPStatusError, UnsupportedProtocol
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import slugify

from .const import CONF_CALENDAR_NAME, CONF_STORAGE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_CALENDAR_NAME): str, vol.Required(CONF_URL): str}
)


class RemoteCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local Calendar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors: dict = {}
        _LOGGER.debug("User input: %s", user_input)
        key = slugify(user_input[CONF_CALENDAR_NAME])
        user_input[CONF_STORAGE_KEY] = key
        self.data = user_input
        client = get_async_client(self.hass)
        _LOGGER.debug("User input in fetch url: %s", user_input)
        if user_input is not None:
            headers: dict = {}
            try:
                await client.get(user_input[CONF_URL], headers=headers)
            except UnsupportedProtocol as err:
                errors["base"] = "unsupported_protocol"
                _LOGGER.debug("Unsupported Protokol: %s", err)
            except ConnectError as err:
                errors["base"] = "url_not_reachable"
                _LOGGER.debug("ConnectError: %s", err)
            except HTTPStatusError as err:
                errors["base"] = "not_authorized"
                _LOGGER.debug("HTTPStatusError: %s", err)
            except ValueError as err:
                errors["base"] = "unknown_url_type"
                _LOGGER.debug("ValueError: %s", err)
            else:
                return self.async_create_entry(
                    title=self.data[CONF_CALENDAR_NAME], data=self.data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
