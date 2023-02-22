"""Config flow for NFAndroidTV integration."""
from __future__ import annotations

import logging
from typing import Any

from notifications_android_tv.notifications import ConnectError, Notifications
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NFAndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NFAndroidTV."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_NAME: user_input[CONF_NAME]}
            )
            if not (error := await self._async_try_connect(user_input[CONF_HOST])):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self, host: str) -> str | None:
        """Try connecting to Android TV / Fire TV."""
        try:
            await self.hass.async_add_executor_job(Notifications, host)
        except ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None
