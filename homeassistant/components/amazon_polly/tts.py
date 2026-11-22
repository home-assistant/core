"""Support for the Amazon Polly text to speech service."""

from enum import StrEnum
import logging
from typing import Any, Final, override

from botocore.exceptions import BotoCoreError, ClientError
import probatio

from homeassistant.components.tts import (
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechCommonOption,
    TtsAudioType,
)
from homeassistant.const import (
    ATTR_CREDENTIALS,
    CONF_PROFILE_NAME,
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.generated.amazon_polly import (
    SUPPORTED_ENGINES,
    SUPPORTED_REGIONS,
    SUPPORTED_VOICES,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
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
    DOMAIN,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_SAMPLE_RATES,
    SUPPORTED_SAMPLE_RATES_MAP,
    SUPPORTED_TEXT_TYPES,
)
from .helpers import AmazonPollyData, CannotConnect, InvalidAuth, async_connect

_LOGGER: Final = logging.getLogger(__name__)


class AmazonPollyTextToSpeechOption(StrEnum):
    """Store keys for the Amazon Polly text-to-speech options."""

    ENGINE = "engine"


PLATFORM_SCHEMA: Final = TTS_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_REGION, default=DEFAULT_REGION): probatio.In(
            SUPPORTED_REGIONS
        ),
        probatio.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        probatio.Inclusive(
            probatio.Secret(CONF_SECRET_ACCESS_KEY), ATTR_CREDENTIALS
        ): cv.string,
        probatio.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
        probatio.Optional(CONF_VOICE, default=DEFAULT_VOICE): probatio.In(
            SUPPORTED_VOICES
        ),
        probatio.Optional(CONF_ENGINE, default=DEFAULT_ENGINE): probatio.In(
            SUPPORTED_ENGINES
        ),
        probatio.Optional(
            CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT
        ): probatio.In(SUPPORTED_OUTPUT_FORMATS),
        probatio.Optional(CONF_SAMPLE_RATE): probatio.All(
            cv.string, probatio.In(SUPPORTED_SAMPLE_RATES)
        ),
        probatio.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): probatio.In(
            SUPPORTED_TEXT_TYPES
        ),
    }
)


async def async_get_engine(
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

    try:
        data = await async_connect(
            hass,
            region=config[CONF_REGION],
            access_key_id=config.get(CONF_ACCESS_KEY_ID),
            secret_access_key=config.get(CONF_SECRET_ACCESS_KEY),
            profile=config.get(CONF_PROFILE_NAME),
        )
    except (CannotConnect, InvalidAuth) as err:
        _LOGGER.error("Unable to connect to Amazon Polly: %s", err)
        return None

    async def _async_close_client(_: Event) -> None:
        await data.client.__aexit__(None, None, None)

    # Legacy providers are never unloaded, so close the client on shutdown.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)

    return AmazonPollyProvider(data, config | {CONF_SAMPLE_RATE: sample_rate})


class AmazonPollyProvider(Provider):
    """Amazon Polly speech api provider."""

    def __init__(self, data: AmazonPollyData, config: ConfigType) -> None:
        """Initialize Amazon Polly provider for TTS."""
        self._data = data
        self._config = config
        self._default_voice: str = config[CONF_VOICE]
        self._default_engine: str = config[CONF_ENGINE]
        self.name = "Amazon Polly"

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._data.languages

    @property
    @override
    def default_language(self) -> str | None:
        """Return the default language."""
        return self._data.voices.get(self._default_voice, {}).get("LanguageCode")

    @property
    @override
    def default_options(self) -> dict[str, str]:
        """Return dict include default options."""
        return {
            TextToSpeechCommonOption.VOICE: self._default_voice,
            AmazonPollyTextToSpeechOption.ENGINE: self._default_engine,
        }

    @property
    @override
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return [TextToSpeechCommonOption.VOICE, AmazonPollyTextToSpeechOption.ENGINE]

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Request TTS file from Polly."""
        voice_id = options.get(TextToSpeechCommonOption.VOICE, self._default_voice)
        if (voice := self._data.voices.get(voice_id)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_voice",
                translation_placeholders={"voice": voice_id},
            )
        if language != voice.get("LanguageCode"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="language_not_supported",
                translation_placeholders={"voice": voice_id, "language": language},
            )
        engine = options.get(AmazonPollyTextToSpeechOption.ENGINE, self._default_engine)
        if voice_id not in self._data.engines.get(engine, set()):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="engine_not_supported",
                translation_placeholders={"voice": voice_id, "engine": engine},
            )

        try:
            response = await self._data.client.synthesize_speech(
                Engine=engine,
                OutputFormat=self._config[CONF_OUTPUT_FORMAT],
                SampleRate=self._config[CONF_SAMPLE_RATE],
                Text=message,
                TextType=self._config[CONF_TEXT_TYPE],
                VoiceId=voice_id,
            )
            async with response["AudioStream"] as stream:
                audio: bytes = await stream.read()
        except (BotoCoreError, ClientError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="synthesis_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        return CONTENT_TYPE_EXTENSIONS[response["ContentType"]], audio
