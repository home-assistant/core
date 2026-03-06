"""Config flow for Pico TTS integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, SUPPORT_LANGUAGES

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_LANG): vol.In(SUPPORT_LANGUAGES)})


class PicoTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pico TTS."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        language = user_input[CONF_LANG]

        self._async_abort_entries_match({CONF_LANG: language})

        title = f"Pico TTS {language}"
        data = {
            CONF_LANG: language,
        }

        return self.async_create_entry(title=title, data=data)

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import Pico TTS config from yaml."""

        return await self.async_step_user(import_info)
