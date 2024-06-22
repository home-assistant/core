"""Config flow for ElevenLabs text-to-speech integration."""

from __future__ import annotations

import logging
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_MODEL, CONF_VOICE, DEFAULT_MODEL, DOMAIN

STEP_USER_DATA_SCHEMA_NO_AUTH = vol.Schema({vol.Required(CONF_API_KEY): str})


_LOGGER = logging.getLogger(__name__)


async def get_voices_models(api_key: str) -> tuple[dict[str, str], dict[str, str]]:
    """Get available voices and models as dicts."""
    client = AsyncElevenLabs(api_key=api_key)
    voices = (await client.voices.get_all()).voices
    models = await client.models.get_all()
    voices_dict = {
        voice.voice_id: voice.name
        for voice in sorted(voices, key=lambda v: v.name or "")
        if voice.name
    }
    models_dict = {
        model.model_id: model.name
        for model in sorted(models, key=lambda m: m.name or "")
        if model.name and model.can_do_text_to_speech
    }
    return voices_dict, models_dict


class ElevenLabsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ElevenLabs text-to-speech."""

    VERSION = 1

    user_info: dict[str, Any] | None = None

    # id -> name
    voices: dict[str, str] = {}
    models: dict[str, str] = {}

    def _get_user_schema_authenticated(self) -> vol.Schema:
        assert self.voices and self.models
        first_voice_id = next(iter(self.voices.keys()))

        return vol.Schema(
            {
                vol.Required(
                    CONF_VOICE, description={"suggested_value": first_voice_id}
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(label=voice_name, value=voice_id)
                            for voice_id, voice_name in self.voices.items()
                        ]
                    )
                ),
                vol.Required(
                    CONF_MODEL, description={"suggested_value": DEFAULT_MODEL}
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(label=model_name, value=model_id)
                            for model_id, model_name in self.models.items()
                        ]
                    )
                ),
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
            self.voices, self.models = await get_voices_models(user_input[CONF_API_KEY])
        except ApiError:
            errors["base"] = "invalid_api_key"
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA_NO_AUTH, errors=errors
            )
        # Set model id
        user_input.setdefault(CONF_MODEL, DEFAULT_MODEL)
        self.user_info = user_input
        return self.async_create_entry(
            title=f"ElevenLabs {self.models[user_input[CONF_MODEL]]}", data=user_input
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return ElevenLabsOptionsFlow(config_entry)


class ElevenLabsOptionsFlow(OptionsFlow):
    """ElevenLabs options flow."""

    # id -> name
    voices: dict[str, str] = {}
    models: dict[str, str] = {}

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.api_key: str = self.config_entry.data[CONF_API_KEY]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if not self.voices or not self.models:
            self.voices, self.models = await get_voices_models(self.api_key)

        assert self.models and self.voices

        if user_input is not None:
            return self.async_create_entry(
                title=f"ElevenLabs {self.models[user_input[CONF_MODEL]]}",
                data=user_input,
            )

        options: dict[str, str] = {
            CONF_MODEL: self.config_entry.options.get(
                CONF_MODEL, self.config_entry.data.get(CONF_MODEL)
            ),
            CONF_VOICE: self.config_entry.options.get(
                CONF_VOICE, self.config_entry.data.get(CONF_VOICE)
            ),
        }

        schema = self.elevenlabs_config_option_schema(options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )

    def elevenlabs_config_option_schema(self, options: dict[str, str]) -> dict:
        """Elevenlabs options schema."""
        return {
            vol.Required(
                CONF_MODEL,
                description={"suggested_value": options[CONF_MODEL]},
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(label=model_name, value=model_id)
                        for model_id, model_name in self.models.items()
                    ]
                )
            ),
            vol.Required(
                CONF_VOICE,
                description={"suggested_value": options[CONF_VOICE]},
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(label=voice_name, value=voice_id)
                        for voice_id, voice_name in self.voices.items()
                    ]
                )
            ),
        }
