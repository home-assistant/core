"""Config flow for picoTTS integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback

from .const import DOMAIN


class PicoTTSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for picoTTS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Prevent multiple instances
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="picoTTS", data={})

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration import from YAML."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="picoTTS", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PicoTTSOptionsFlow:
        """Return the options flow handler."""
        return PicoTTSOptionsFlow(config_entry)


class PicoTTSOptionsFlow(config_entries.OptionsFlow):
    """Options flow for picoTTS (none required)."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """No options available."""
        return self.async_create_entry(title="", data={})
