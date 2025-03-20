"""Config flow for Switcher integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from aioswitcher.bridge import SwitcherBase
from aioswitcher.device.tools import validate_token
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_USERNAME

from .const import DOMAIN
from .utils import async_discover_devices

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=""): str,
        vol.Required(CONF_TOKEN, default=""): str,
    }
)


class SwitcherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    VERSION = 1

    username: str | None = None
    token: str | None = None
    discovered_devices: dict[str, SwitcherBase] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        self.discovered_devices = await async_discover_devices()

        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of the config flow."""
        if len(self.discovered_devices) == 0:
            return self.async_abort(reason="no_devices_found")

        for device_id, device in self.discovered_devices.items():
            if device.token_needed:
                _LOGGER.debug("Device with ID %s requires a token", device_id)
                return await self.async_step_credentials()
        return await self._create_entry()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.username = user_input.get(CONF_USERNAME)
            self.token = user_input.get(CONF_TOKEN)

            token_is_valid = await validate_token(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if token_is_valid:
                return await self._create_entry()
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="credentials", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token_is_valid = await validate_token(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if token_is_valid:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CONFIG_SCHEMA,
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
