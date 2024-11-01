"""Config flow for Google Translate text-to-speech integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_TLD,
    DEFAULT_LANG,
    DEFAULT_TLD,
    DOMAIN,
    SUPPORT_LANGUAGES,
    SUPPORT_TLD,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_TLD, default=DEFAULT_TLD): vol.In(SUPPORT_TLD),
    }
)


class GoogleTranslateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Translate text-to-speech."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_LANG: user_input[CONF_LANG],
                    CONF_TLD: user_input[CONF_TLD],
                }
            )
            return self.async_create_entry(
                title="Google Translate text-to-speech", data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(
            title="Google Translate text-to-speech",
            data={CONF_LANG: DEFAULT_LANG, CONF_TLD: DEFAULT_TLD},
        )
