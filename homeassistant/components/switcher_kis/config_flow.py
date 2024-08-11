"""Config flow for Switcher integration."""

from __future__ import annotations

from homeassistant.auth import InvalidAuthError
from homeassistant.components.dlna_dms.dms import DeviceConnectionError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from typing import Any

from .const import DOMAIN, DATA_DISCOVERY, CONF_USERNAME, CONF_TOKEN
from .utils import async_discover_devices, validate_token
import voluptuous as vol


class SwitcherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._username: str | None = None
        self._token: str | None = None

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

        return self.async_create_entry(
            title="Switcher",
            data={
                CONF_USERNAME: self._username,
                CONF_TOKEN: self._token,
            },
        )

    async def async_step_reauth(self, user_input: dict[str, Any]) -> ConfigFlowResult:
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
            # token_is_valid = validate_token(
            #     entry.data.get(CONF_USERNAME), entry.data.get(CONF_TOKEN)
            # )
            # if token_is_valid:
            #     _LOGGER.info("Token is valid")
            # else:
            #     _LOGGER.info("Token is invalid")

            # try:
            #     await validate_token(user_input)
            # except (DeviceConnectionError, InvalidAuthError):
            #     return self.async_abort(reason="reauth_unsuccessful")

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
