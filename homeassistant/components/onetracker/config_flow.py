"""Config flow for OneTracker."""
from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import OneTrackerAPI, OneTrackerAPIException
from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    OneTrackerAPI(data)


class OneTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OneTracker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OneTrackerOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OneTrackerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            try:
                _LOGGER.info("Input %s", json.dumps(user_input))
                await self.hass.async_add_executor_job(_validate_input, user_input)
            except OneTrackerAPIException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        data_schema = {
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors or {},
        )


class OneTrackerOptionsFlowHandler(OptionsFlow):
    """Handle OneTracker client options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage OneTracker options."""
        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        options = {
            vol.Required(CONF_EMAIL, default=self.config_entry.data[CONF_EMAIL]): str,
            vol.Required(
                CONF_PASSWORD, default=self.config_entry.data[CONF_PASSWORD]
            ): str,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
