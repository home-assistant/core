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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_CONFIGURE_VOICE,
    CONF_MODEL,
    CONF_OPTIMIZE_LATENCY,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_MODEL,
    DEFAULT_OPTIMIZE_LATENCY,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
)

USER_STEP_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


_LOGGER = logging.getLogger(__name__)


async def get_voices_models(
    hass: HomeAssistant, api_key: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Get available voices and models as dicts."""
    httpx_client = get_async_client(hass)
    client = AsyncElevenLabs(api_key=api_key, httpx_client=httpx_client)
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
                voices, _ = await get_voices_models(self.hass, user_input[CONF_API_KEY])
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


class ElevenLabsOptionsFlow(OptionsFlow):
    """ElevenLabs options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.api_key: str = config_entry.data[CONF_API_KEY]
        # id -> name
        self.voices: dict[str, str] = {}
        self.models: dict[str, str] = {}
        self.model: str | None = None
        self.voice: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if not self.voices or not self.models:
            self.voices, self.models = await get_voices_models(self.hass, self.api_key)

        assert self.models and self.voices

        if user_input is not None:
            self.model = user_input[CONF_MODEL]
            self.voice = user_input[CONF_VOICE]
            configure_voice = user_input.pop(CONF_CONFIGURE_VOICE)
            if configure_voice:
                return await self.async_step_voice_settings()
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
                    vol.Required(CONF_CONFIGURE_VOICE, default=False): bool,
                }
            ),
            self.config_entry.options,
        )

    async def async_step_voice_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle voice settings."""
        assert self.voices and self.models
        if user_input is not None:
            user_input[CONF_MODEL] = self.model
            user_input[CONF_VOICE] = self.voice
            return self.async_create_entry(
                title="ElevenLabs",
                data=user_input,
            )
        return self.async_show_form(
            step_id="voice_settings",
            data_schema=self.elevenlabs_config_options_voice_schema(),
        )

    def elevenlabs_config_options_voice_schema(self) -> vol.Schema:
        """Elevenlabs options voice schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_STABILITY,
                    default=self.config_entry.options.get(
                        CONF_STABILITY, DEFAULT_STABILITY
                    ),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0, max=1),
                ),
                vol.Optional(
                    CONF_SIMILARITY,
                    default=self.config_entry.options.get(
                        CONF_SIMILARITY, DEFAULT_SIMILARITY
                    ),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0, max=1),
                ),
                vol.Optional(
                    CONF_OPTIMIZE_LATENCY,
                    default=self.config_entry.options.get(
                        CONF_OPTIMIZE_LATENCY, DEFAULT_OPTIMIZE_LATENCY
                    ),
                ): vol.All(int, vol.Range(min=0, max=4)),
                vol.Optional(
                    CONF_STYLE,
                    default=self.config_entry.options.get(CONF_STYLE, DEFAULT_STYLE),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0, max=1),
                ),
                vol.Optional(
                    CONF_USE_SPEAKER_BOOST,
                    default=self.config_entry.options.get(
                        CONF_USE_SPEAKER_BOOST, DEFAULT_USE_SPEAKER_BOOST
                    ),
                ): bool,
            }
        )
