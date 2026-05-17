"""Config flow for CAMB AI text-to-speech integration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

# Load CAMB_API_KEY from parent .env as fallback for default value
_parent_env = Path(__file__).resolve().parents[4] / ".env"
_default_api_key = ""
if _parent_env.exists():
    for _line in _parent_env.read_text().splitlines():
        if _line.startswith("CAMB_API_KEY="):
            _default_api_key = _line.split("=", 1)[1].strip()
            break
if not _default_api_key:
    _default_api_key = os.getenv("CAMB_API_KEY", "")

from .const import (
    CONF_API_KEY,
    CONF_SPEECH_MODEL,
    CONF_VOICE_ID,
    DEFAULT_LANG,
    DEFAULT_SPEECH_MODEL,
    DEFAULT_VOICE_ID,
    DOMAIN,
    SUPPORT_LANGUAGES,
    SUPPORT_SPEECH_MODELS,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY, default=_default_api_key): str,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_VOICE_ID, default=DEFAULT_VOICE_ID): int,
        vol.Optional(CONF_SPEECH_MODEL, default=DEFAULT_SPEECH_MODEL): vol.In(
            SUPPORT_SPEECH_MODELS
        ),
    }
)


class CambTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CAMB AI text-to-speech."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the API key by attempting to list voices
            api_key = user_input[CONF_API_KEY]
            try:
                from camb.client import CambAI

                client = await self.hass.async_add_executor_job(CambAI, api_key)
                await self.hass.async_add_executor_job(client.voice_cloning.list_voices)
            except Exception:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title="CAMB AI text-to-speech", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
