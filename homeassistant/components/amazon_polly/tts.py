"""Support for the Amazon Polly text to speech service."""

from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any, Final

import boto3
import botocore
import voluptuous as vol

from homeassistant.components.tts import (
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TtsAudioType,
)
from homeassistant.const import ATTR_CREDENTIALS, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.generated.amazon_polly import (
    SUPPORTED_ENGINES,
    SUPPORTED_REGIONS,
    SUPPORTED_VOICES,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    AWS_CONF_CONNECT_TIMEOUT,
    AWS_CONF_MAX_POOL_CONNECTIONS,
    AWS_CONF_READ_TIMEOUT,
    CONF_ACCESS_KEY_ID,
    CONF_ENGINE,
    CONF_OUTPUT_FORMAT,
    CONF_REGION,
    CONF_SAMPLE_RATE,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEXT_TYPE,
    CONF_VOICE,
    CONTENT_TYPE_EXTENSIONS,
    DEFAULT_ENGINE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_REGION,
    DEFAULT_SAMPLE_RATES,
    DEFAULT_TEXT_TYPE,
    DEFAULT_VOICE,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_SAMPLE_RATES,
    SUPPORTED_SAMPLE_RATES_MAP,
    SUPPORTED_TEXT_TYPES,
)

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = TTS_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
        vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
        vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORTED_VOICES),
        vol.Optional(CONF_ENGINE, default=DEFAULT_ENGINE): vol.In(SUPPORTED_ENGINES),
        vol.Optional(CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT): vol.In(
            SUPPORTED_OUTPUT_FORMATS
        ),
        vol.Optional(CONF_SAMPLE_RATE): vol.All(
            cv.string, vol.In(SUPPORTED_SAMPLE_RATES)
        ),
        vol.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): vol.In(
            SUPPORTED_TEXT_TYPES
        ),
    }
)


def get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Provider | None:
    """Set up Amazon Polly speech component."""
    output_format = config[CONF_OUTPUT_FORMAT]
    sample_rate = config.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATES[output_format])
    if sample_rate not in SUPPORTED_SAMPLE_RATES_MAP[output_format]:
        _LOGGER.error(
            "%s is not a valid sample rate for %s", sample_rate, output_format
        )
        return None

    config[CONF_SAMPLE_RATE] = sample_rate

    profile: str | None = config.get(CONF_PROFILE_NAME)

    if profile is not None:
        boto3.setup_default_session(profile_name=profile)

    aws_config = {
        CONF_REGION: config[CONF_REGION],
        CONF_ACCESS_KEY_ID: config.get(CONF_ACCESS_KEY_ID),
        CONF_SECRET_ACCESS_KEY: config.get(CONF_SECRET_ACCESS_KEY),
        "config": botocore.config.Config(
            connect_timeout=AWS_CONF_CONNECT_TIMEOUT,
            read_timeout=AWS_CONF_READ_TIMEOUT,
            max_pool_connections=AWS_CONF_MAX_POOL_CONNECTIONS,
        ),
    }

    del config[CONF_REGION]
    del config[CONF_ACCESS_KEY_ID]
    del config[CONF_SECRET_ACCESS_KEY]

    polly_client = boto3.client("polly", **aws_config)

    supported_languages: list[str] = []

    all_voices: dict[str, dict[str, str]] = {}

    all_engines: dict[str, set[str]] = defaultdict(set)

    all_voices_req = polly_client.describe_voices()

    for voice in all_voices_req.get("Voices", []):
        voice_id: str | None = voice.get("Id")
        if voice_id is None:
            continue
        all_voices[voice_id] = voice
        language_code: str | None = voice.get("LanguageCode")
        if language_code is not None and language_code not in supported_languages:
            supported_languages.append(language_code)
        for engine in voice.get("SupportedEngines"):
            all_engines[engine].add(voice_id)

    return AmazonPollyProvider(
        polly_client, config, supported_languages, all_voices, all_engines
    )


class AmazonPollyProvider(Provider):
    """Amazon Polly speech api provider."""

    def __init__(
        self,
        polly_client: boto3.client,
        config: ConfigType,
        supported_languages: list[str],
        all_voices: dict[str, dict[str, str]],
        all_engines: dict[str, set[str]],
    ) -> None:
        """Initialize Amazon Polly provider for TTS."""
        self.client = polly_client
        self.config = config
        self.supported_langs = supported_languages
        self.all_voices = all_voices
        self.all_engines = all_engines
        self.default_voice: str = self.config[CONF_VOICE]
        self.default_engine: str = self.config[CONF_ENGINE]
        self.name = "Amazon Polly"

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self.supported_langs

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return self.all_voices.get(self.default_voice, {}).get("LanguageCode")

    @property
    def default_options(self) -> dict[str, str]:
        """Return dict include default options."""
        return {CONF_VOICE: self.default_voice, CONF_ENGINE: self.default_engine}

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return [CONF_VOICE, CONF_ENGINE]

    def get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Request TTS file from Polly."""
        voice_id = options.get(CONF_VOICE, self.default_voice)
        voice_in_dict = self.all_voices[voice_id]
        if language != voice_in_dict.get("LanguageCode"):
            _LOGGER.error("%s does not support the %s language", voice_id, language)
            return None, None

        engine = options.get(CONF_ENGINE, self.default_engine)
        if voice_id not in self.all_engines[engine]:
            _LOGGER.error("%s does not support the %s engine", voice_id, engine)
            return None, None

        _LOGGER.debug("Requesting TTS file for text: %s", message)
        resp = self.client.synthesize_speech(
            Engine=engine,
            OutputFormat=self.config[CONF_OUTPUT_FORMAT],
            SampleRate=self.config[CONF_SAMPLE_RATE],
            Text=message,
            TextType=self.config[CONF_TEXT_TYPE],
            VoiceId=voice_id,
        )

        _LOGGER.debug("Reply received for TTS: %s", message)
        return (
            CONTENT_TYPE_EXTENSIONS[resp.get("ContentType")],
            resp.get("AudioStream").read(),
        )
