"""Config flow for NFAndroidTV integration."""

from __future__ import annotations

import logging
from typing import Any

from notifications_android_tv.notifications import ConnectError, Notifications
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NFAndroidTVFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NFAndroidTV."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if not (error := await self._async_try_connect(user_input[CONF_HOST])):
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow for Notification for Android TV / Fire TV."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            if not (error := await self._async_try_connect(user_input[CONF_HOST])):
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                suggested_values=user_input or entry.data,
            ),
            description_placeholders={CONF_NAME: entry.title},
            errors=errors,
        )

    async def _async_try_connect(self, host: str) -> str | None:
        """Try connecting to Android TV / Fire TV."""
        try:
            await self.hass.async_add_executor_job(Notifications, host)
        except ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None
