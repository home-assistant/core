"""Config flow for ElevenLabs text-to-speech integration."""

from __future__ import annotations

import logging
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .const import CONF_MODEL, CONF_VOICE, DOMAIN

STEP_USER_DATA_SCHEMA_NO_AUTH = vol.Schema({vol.Required(CONF_API_KEY): str})


_LOGGER = logging.getLogger(__name__)


class ElevenLabsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ElevenLabs text-to-speech."""

    VERSION = 1
    MINOR_VERSION = 1

    user_info: dict[str, Any] | None = None
    voices: list[str] | None = None
    models: list[str] | None = None

    async def _get_voices_models(self, user_input: dict[str, Any]) -> None:
        client = AsyncElevenLabs(api_key=user_input[CONF_API_KEY])
        voices_async = client.voices.get_all()
        models_async = client.models.get_all()
        voices: list[Voice] = (await voices_async).voices
        models: list[Model] = await models_async
        voice_names = [voice.name if voice.name else "Unknown" for voice in voices]
        self.voices = voice_names
        model_names = [model.name if model.name else "Unknown" for model in models]
        self.models = model_names

    def _get_user_schema_authenticated(self) -> vol.Schema:
        if self.voices is None or self.models is None:
            raise ValueError("Voices or models are not set")
        default_voice = sorted(self.voices)[0]
        default_model = sorted(self.models)[0]
        return vol.Schema(
            {
                vol.Optional(CONF_VOICE, default=default_voice): vol.In(self.voices),
                vol.Optional(CONF_MODEL, default=default_model): vol.In(self.models),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA_NO_AUTH
            )
        # Validate auth, get voices
        try:
            await self._get_voices_models(user_input)
        except KeyError:
            errors[CONF_API_KEY] = "No API-Key provided"
        except ApiError:
            errors[CONF_API_KEY] = "ElevenLabs API responded with an Error!"
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA_NO_AUTH, errors=errors
            )

        self.user_info = user_input
        return await self.async_step_voice()

    async def async_step_voice(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the voice selection step."""
        if user_input is None:
            return self.async_show_form(
                step_id="voice", data_schema=self._get_user_schema_authenticated()
            )
        # Add api_key to user input
        if self.user_info is None:
            raise ValueError("User info is not set")
        user_input[CONF_API_KEY] = self.user_info.get(CONF_API_KEY)
        return self.async_create_entry(
            title="ElevenLabs text-to-speech", data=user_input
        )
