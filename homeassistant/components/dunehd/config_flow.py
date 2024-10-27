"""Adds config flow for Dune HD integration."""

from __future__ import annotations

from typing import Any

from pdunehd import DuneHDPlayer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_host_valid

from .const import DOMAIN


class DuneHDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dune HD integration."""

    VERSION = 1

    async def init_device(self, host: str) -> None:
        """Initialize Dune HD player."""
        player = DuneHDPlayer(host)
        state = await self.hass.async_add_executor_job(player.update_state)
        if not state:
            raise CannotConnect

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if is_host_valid(user_input[CONF_HOST]):
                host: str = user_input[CONF_HOST]

                try:
                    if self.host_already_configured(host):
                        raise AlreadyConfigured  # noqa: TRY301
                    await self.init_device(host)
                except CannotConnect:
                    errors[CONF_HOST] = "cannot_connect"
                except AlreadyConfigured:
                    errors[CONF_HOST] = "already_configured"
                else:
                    return self.async_create_entry(title=host, data=user_input)
            else:
                errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
            errors=errors,
        )

    def host_already_configured(self, host: str) -> bool:
        """See if we already have a dunehd entry matching user input configured."""
        existing_hosts = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        return host in existing_hosts


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate device is already configured."""
