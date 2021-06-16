"""Config flow for Mikrotik."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_REPEATER_MODE,
    CONF_TRACK_WIRED,
    DEFAULT_API_PORT,
    DEFAULT_ARP_PING,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACK_WIRED,
    DOMAIN,
)
from .errors import CannotConnect, LoginError
from .hub import get_api


class MikrotikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Mikrotik config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return MikrotikOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(CONF_HOST)
            self._abort_if_unique_id_configured()

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
        form_fields = {
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): int,
            vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        }
        if self._async_current_entries():
            form_fields.update({vol.Optional(CONF_REPEATER_MODE, default=False): bool})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(form_fields),
            errors=errors,
        )


class MikrotikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mikrotik options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Mikrotik options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Manage the Mikrotik options."""
        return await self.async_step_device_tracker()

    async def async_step_device_tracker(self, user_input: dict[str, Any] = None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_TRACK_WIRED,
                default=self.config_entry.options.get(
                    CONF_TRACK_WIRED, DEFAULT_TRACK_WIRED
                ),
            ): bool,
            vol.Optional(
                CONF_ARP_PING,
                default=self.config_entry.options.get(CONF_ARP_PING, DEFAULT_ARP_PING),
            ): bool,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
        }

        if not self.hass.data[DOMAIN][self.config_entry.entry_id].api.repeater_mode:
            options.update(
                {
                    vol.Optional(
                        CONF_DETECTION_TIME,
                        default=self.config_entry.options.get(
                            CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                        ),
                    ): int,
                }
            )

        return self.async_show_form(
            step_id="device_tracker", data_schema=vol.Schema(options)
        )
