"""Helper classes for Google Cloud integration."""

from __future__ import annotations

import functools
import operator
from types import MappingProxyType
from typing import Any

from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ENCODING,
    CONF_GAIN,
    CONF_GENDER,
    CONF_KEY_FILE,
    CONF_PITCH,
    CONF_PROFILES,
    CONF_SPEED,
    CONF_TEXT_TYPE,
    CONF_VOICE,
    DEFAULT_LANG,
)

DEFAULT_VOICE = ""


async def async_tts_voices(
    client: texttospeech.TextToSpeechAsyncClient,
) -> dict[str, list[str]]:
    """Get TTS voice model names keyed by language."""
    voices: dict[str, list[str]] = {}
    list_voices_response = await client.list_voices()
    for voice in list_voices_response.voices:
        language_code = voice.language_codes[0]
        if language_code not in voices:
            voices[language_code] = []
        voices[language_code].append(voice.name)
    return voices


def tts_options_schema(
    config_options: MappingProxyType[str, Any], voices: dict[str, list[str]]
):
    """Return schema for TTS options with default values from config or constants."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_GENDER,
                description={"suggested_value": config_options.get(CONF_GENDER)},
                default=config_options.get(
                    CONF_GENDER,
                    texttospeech.SsmlVoiceGender.NEUTRAL.name,  # type: ignore[attr-defined]
                ),
            ): vol.All(
                vol.Upper,
                SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=list(texttospeech.SsmlVoiceGender.__members__),
                    )
                ),
            ),
            vol.Optional(
                CONF_VOICE,
                description={"suggested_value": config_options.get(CONF_VOICE)},
                default=config_options.get(CONF_VOICE, DEFAULT_VOICE),
            ): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.DROPDOWN,
                    options=["", *functools.reduce(operator.iadd, voices.values(), [])],
                )
            ),
            vol.Optional(
                CONF_ENCODING,
                description={"suggested_value": config_options.get(CONF_ENCODING)},
                default=config_options.get(
                    CONF_ENCODING,
                    texttospeech.AudioEncoding.MP3.name,  # type: ignore[attr-defined]
                ),
            ): vol.All(
                vol.Upper,
                SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=list(texttospeech.AudioEncoding.__members__),
                    )
                ),
            ),
            vol.Optional(
                CONF_SPEED,
                description={"suggested_value": config_options.get(CONF_SPEED)},
                default=config_options.get(CONF_SPEED, 1.0),
            ): NumberSelector(NumberSelectorConfig(min=0.25, max=4.0, step=0.01)),
            vol.Optional(
                CONF_PITCH,
                description={"suggested_value": config_options.get(CONF_PITCH)},
                default=config_options.get(CONF_PITCH, 0),
            ): NumberSelector(NumberSelectorConfig(min=-20.0, max=20.0, step=0.1)),
            vol.Optional(
                CONF_GAIN,
                description={"suggested_value": config_options.get(CONF_GAIN)},
                default=config_options.get(CONF_GAIN, 0),
            ): NumberSelector(NumberSelectorConfig(min=-96.0, max=16.0, step=0.1)),
            vol.Optional(
                CONF_PROFILES,
                description={"suggested_value": config_options.get(CONF_PROFILES)},
                default=config_options.get(CONF_PROFILES, []),
            ): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.DROPDOWN,
                    options=[
                        # https://cloud.google.com/text-to-speech/docs/audio-profiles
                        "wearable-class-device",
                        "handset-class-device",
                        "headphone-class-device",
                        "small-bluetooth-speaker-class-device",
                        "medium-bluetooth-speaker-class-device",
                        "large-home-entertainment-class-device",
                        "large-automotive-class-device",
                        "telephony-class-application",
                    ],
                    multiple=True,
                    sort=False,
                )
            ),
            vol.Optional(
                CONF_TEXT_TYPE,
                description={"suggested_value": config_options.get(CONF_TEXT_TYPE)},
                default=config_options.get(CONF_TEXT_TYPE, "text"),
            ): vol.All(
                vol.Lower,
                SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=["text", "ssml"],
                    )
                ),
            ),
        }
    )


def tts_platform_schema():
    """Return schema for TTS platform."""
    return vol.Schema(
        {
            vol.Optional(CONF_KEY_FILE): cv.string,
            vol.Optional(CONF_LANG, default=DEFAULT_LANG): cv.matches_regex(
                r"[a-z]{2,3}-[A-Z]{2}|"
            ),
            **tts_options_schema({}, {}).schema,
            vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.matches_regex(
                r"[a-z]{2,3}-[A-Z]{2}-.*-[A-Z]|"
            ),
        }
    )
