"""Config flow for Mikrotik."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_API_PORT,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DOMAIN,
)
from .errors import CannotConnect, LoginError
from .hub import get_api


class MikrotikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Mikrotik config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MikrotikOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MikrotikOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            for entry in self._async_current_entries():
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            try:
                await self.hass.async_add_executor_job(get_api, self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except LoginError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): int,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )


class MikrotikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mikrotik options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Mikrotik options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Mikrotik options."""
        return await self.async_step_device_tracker()

    async def async_step_device_tracker(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_FORCE_DHCP,
                default=self.config_entry.options.get(CONF_FORCE_DHCP, False),
            ): bool,
            vol.Optional(
                CONF_ARP_PING,
                default=self.config_entry.options.get(CONF_ARP_PING, False),
            ): bool,
            vol.Optional(
                CONF_DETECTION_TIME,
                default=self.config_entry.options.get(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                ),
            ): int,
        }

        return self.async_show_form(
            step_id="device_tracker", data_schema=vol.Schema(options)
        )
