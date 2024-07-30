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
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_MODEL, CONF_VOICE, DEFAULT_MODEL, DOMAIN

USER_STEP_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                voices, _ = await get_voices_models(user_input[CONF_API_KEY])
            except ApiError:
                errors["base"] = "invalid_api_key"
            else:
                return self.async_create_entry(
                    title="ElevenLabs",
                    data=user_input,
                    options={CONF_MODEL: DEFAULT_MODEL, CONF_VOICE: list(voices)[0]},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_STEP_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return ElevenLabsOptionsFlow(config_entry)


class ElevenLabsOptionsFlow(OptionsFlowWithConfigEntry):
    """ElevenLabs options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)
        self.api_key: str = self.config_entry.data[CONF_API_KEY]
        # id -> name
        self.voices: dict[str, str] = {}
        self.models: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if not self.voices or not self.models:
            self.voices, self.models = await get_voices_models(self.api_key)

        assert self.models and self.voices

        if user_input is not None:
            return self.async_create_entry(
                title="ElevenLabs",
                data=user_input,
            )

        schema = self.elevenlabs_config_option_schema()
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    def elevenlabs_config_option_schema(self) -> vol.Schema:
        """Elevenlabs options schema."""
        return self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
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
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(label=voice_name, value=voice_id)
                                for voice_id, voice_name in self.voices.items()
                            ]
                        )
                    ),
                }
            ),
            self.options,
        )
