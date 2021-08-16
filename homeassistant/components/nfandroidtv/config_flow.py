"""Config flow for NFAndroidTV integration."""
from __future__ import annotations

import logging

from notifications_android_tv.notifications import ConnectError, Notifications
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NFAndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NFAndroidTV."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            error = await self._async_try_connect(host)
            if error is None:
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "Already configured. This yaml configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")
        if CONF_NAME not in import_config:
            import_config[CONF_NAME] = f"{DEFAULT_NAME} {import_config[CONF_HOST]}"

        return await self.async_step_user(import_config)

    async def _async_try_connect(self, host):
        """Try connecting to Android TV / Fire TV."""
        try:
            await self.hass.async_add_executor_job(Notifications, host)
        except ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return
