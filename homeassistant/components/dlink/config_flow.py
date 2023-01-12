"""Config flow for the D-Link Power Plug integration."""
from __future__ import annotations

import logging
from typing import Any

from pyW215.pyW215 import SmartPlug
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_USE_LEGACY_PROTOCOL, DEFAULT_NAME, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DLinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for D-Link Power Plug."""

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry."""
        self._async_abort_entries_match({CONF_HOST: config[CONF_HOST]})
        title = config.pop(CONF_NAME, DEFAULT_NAME)
        return self.async_create_entry(
            title=title,
            data=config,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            error = await self.hass.async_add_executor_job(
                self._try_connect, user_input
            )
            if error is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_USE_LEGACY_PROTOCOL): bool,
                }
            ),
            errors=errors,
        )

    def _try_connect(self, user_input: dict[str, Any]) -> str | None:
        """Try connecting to D-Link Power Plug."""
        try:
            smartplug = SmartPlug(
                user_input[CONF_HOST],
                user_input[CONF_PASSWORD],
                user_input[CONF_USERNAME],
                user_input[CONF_USE_LEGACY_PROTOCOL],
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
            return "unknown"
        if smartplug.authenticated:
            return None
        return "cannot_connect"
