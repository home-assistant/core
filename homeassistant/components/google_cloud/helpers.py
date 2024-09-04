"""Helper classes for Google Cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import functools
import operator
from typing import Any

from google.cloud import texttospeech
from google.oauth2.service_account import Credentials
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
    config_options: dict[str, Any],
    voices: dict[str, list[str]],
    from_config_flow: bool = False,
) -> vol.Schema:
    """Return schema for TTS options with default values from config or constants."""
    # If we are called from the config flow we want the defaults to be from constants
    # to allow clearing the current value (passed as suggested_value) in the UI.
    # If we aren't called from the config flow we want the defaults to be from the config.
    defaults = {} if from_config_flow else config_options
    return vol.Schema(
        {
            vol.Optional(
                CONF_GENDER,
                default=defaults.get(
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
                default=defaults.get(CONF_VOICE, DEFAULT_VOICE),
            ): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.DROPDOWN,
                    options=["", *functools.reduce(operator.iadd, voices.values(), [])],
                )
            ),
            vol.Optional(
                CONF_ENCODING,
                default=defaults.get(
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
                default=defaults.get(CONF_SPEED, 1.0),
            ): NumberSelector(NumberSelectorConfig(min=0.25, max=4.0, step=0.01)),
            vol.Optional(
                CONF_PITCH,
                default=defaults.get(CONF_PITCH, 0),
            ): NumberSelector(NumberSelectorConfig(min=-20.0, max=20.0, step=0.1)),
            vol.Optional(
                CONF_GAIN,
                default=defaults.get(CONF_GAIN, 0),
            ): NumberSelector(NumberSelectorConfig(min=-96.0, max=16.0, step=0.1)),
            vol.Optional(
                CONF_PROFILES,
                default=defaults.get(CONF_PROFILES, []),
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
                default=defaults.get(CONF_TEXT_TYPE, "text"),
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


def tts_platform_schema() -> vol.Schema:
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


def validate_service_account_info(info: Mapping[str, str]) -> None:
    """Validate service account info.

    Args:
        info: The service account info in Google format.

    Raises:
        ValueError: If the info is not in the expected format.

    """
    Credentials.from_service_account_info(info)  # type:ignore[no-untyped-call]
