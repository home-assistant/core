"""Config flow for Switcher integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult

from .const import CONF_TOKEN, CONF_USERNAME, DATA_DISCOVERY, DOMAIN
from .utils import async_discover_devices, validate_input

_LOGGER = logging.getLogger(__name__)


class SwitcherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    VERSION = 1

    entry: ConfigEntry | None = None
    username: str | None = None
    token: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if self._async_current_entries(True):
            return self.async_abort(reason="single_instance_allowed")

        self.hass.data.setdefault(DOMAIN, {})
        if DATA_DISCOVERY not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][DATA_DISCOVERY] = self.hass.async_create_task(
                async_discover_devices()
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of the config flow."""
        discovered_devices = await self.hass.data[DOMAIN][DATA_DISCOVERY]

        if len(discovered_devices) == 0:
            self.hass.data[DOMAIN].pop(DATA_DISCOVERY)
            return self.async_abort(reason="no_devices_found")

        for device_id, device in discovered_devices.items():
            if device.token_needed:
                _LOGGER.info("Device with ID %s requires a token", device_id)
                return await self.async_step_credentials()

        return self._create_entry()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.username = user_input.get(CONF_USERNAME)
            self.token = user_input.get(CONF_TOKEN)

            token_is_valid = await validate_input(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if token_is_valid:
                return self._create_entry()
            errors["base"] = "invalid_auth"
        else:
            user_input = {}

        schema = {
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_TOKEN, default=user_input.get(CONF_TOKEN, "")): str,
        }

        return self.async_show_form(
            step_id="credentials", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        assert self.entry is not None

        if user_input is not None:
            token_is_valid = await validate_input(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if not token_is_valid:
                return self.async_abort(reason="reauth_unsuccessful")

            return self.async_update_reload_and_abort(
                self.entry, data={**self.entry.data, **user_input}
            )

        schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_TOKEN): str,
        }
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def _create_entry(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title="Switcher",
            data={
                CONF_USERNAME: self.username,
                CONF_TOKEN: self.token,
            },
        )
