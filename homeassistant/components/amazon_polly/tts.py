"""Support for the Amazon Polly text to speech service."""

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, Final

from botocore.exceptions import BotoCoreError, ClientError
import probatio

from homeassistant.components.tts import (
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechCommonOption,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_CREDENTIALS,
    CONF_PROFILE_NAME,
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.generated.amazon_polly import (
    SUPPORTED_ENGINES,
    SUPPORTED_REGIONS,
    SUPPORTED_VOICES,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
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
from .helpers import (
    AmazonPollyConfigEntry,
    AmazonPollyData,
    CannotConnect,
    InvalidAuth,
    async_connect,
)

_LOGGER: Final = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

BREAKS_IN_HA_VERSION: Final = "2027.6.0"

# Engine used when a voice doesn't support the configured default.
ENGINE_PREFERENCE: Final = ("neural", "generative", "long-form", "standard")

# Language of the default voice, used when it is not offered in the region.
DEFAULT_LANGUAGE: Final = "en-US"


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
    """Set up the legacy YAML Amazon Polly speech provider."""
    output_format = config[CONF_OUTPUT_FORMAT]
    sample_rate = config.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATES[output_format])
    if sample_rate not in SUPPORTED_SAMPLE_RATES_MAP[output_format]:
        _LOGGER.error(
            "%s is not a valid sample rate for %s", sample_rate, output_format
        )
        return None

    if CONF_ACCESS_KEY_ID in config:
        hass.async_create_task(_async_import(hass, config), eager_start=True)
    else:
        _async_create_deprecation_issue(
            hass, "deprecated_yaml_import_issue_credentials"
        )

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


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Import the YAML configuration into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
    )
    if (
        result["type"] is FlowResultType.CREATE_ENTRY
        or result.get("reason") == "already_configured"
    ):
        _async_create_deprecation_issue(hass, "deprecated_yaml")
    else:
        _async_create_deprecation_issue(
            hass, f"deprecated_yaml_import_issue_{result['reason']}"
        )


@callback
def _async_create_deprecation_issue(hass: HomeAssistant, translation_key: str) -> None:
    async_create_issue(
        hass,
        DOMAIN,
        translation_key,
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Amazon Polly",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AmazonPollyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Amazon Polly text-to-speech entity."""
    async_add_entities([AmazonPollyTTSEntity(config_entry)])


class AmazonPollyBase:
    """Speech synthesis shared by the entity and the legacy provider."""

    def __init__(self, data: AmazonPollyData, options: Mapping[str, Any]) -> None:
        """Initialize from the loaded voices and the configured defaults."""
        self._data = data
        self._default_voice: str = options.get(CONF_VOICE, DEFAULT_VOICE)
        self._default_engine: str = options.get(CONF_ENGINE, DEFAULT_ENGINE)
        self._text_type: str = options.get(CONF_TEXT_TYPE, DEFAULT_TEXT_TYPE)
        self._output_format: str = options.get(
            CONF_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT
        )
        self._sample_rate: str = options.get(
            CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATES[self._output_format]
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._data.languages

    @property
    def default_language(self) -> str:
        """Return the default voice's language."""
        language: str = self._data.voices.get(self._default_voice, {}).get(
            "LanguageCode", DEFAULT_LANGUAGE
        )
        return language

    @property
    def default_options(self) -> dict[str, str]:
        """Return the default options."""
        return {TextToSpeechCommonOption.VOICE: self._default_voice}

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return [TextToSpeechCommonOption.VOICE, AmazonPollyTextToSpeechOption.ENGINE]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices for a language."""
        return sorted(
            (
                Voice(voice_id, voice.get("Name", voice_id))
                for voice_id, voice in self._data.voices.items()
                if voice.get("LanguageCode") == language
            ),
            key=lambda voice: voice.name,
        )

    def _engine_for(self, voice_id: str) -> str:
        """Return the default engine, or the best one the voice supports."""
        supported = self._data.voices[voice_id].get("SupportedEngines", [])
        if self._default_engine in supported:
            return self._default_engine
        return next(
            (engine for engine in ENGINE_PREFERENCE if engine in supported),
            self._default_engine,
        )

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Request speech from Amazon Polly."""
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
        engine = options.get(AmazonPollyTextToSpeechOption.ENGINE) or self._engine_for(
            voice_id
        )
        if voice_id not in self._data.engines.get(engine, set()):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="engine_not_supported",
                translation_placeholders={"voice": voice_id, "engine": engine},
            )

        try:
            response = await self._data.client.synthesize_speech(
                Engine=engine,
                OutputFormat=self._output_format,
                SampleRate=self._sample_rate,
                Text=message,
                TextType=self._text_type,
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


class AmazonPollyTTSEntity(AmazonPollyBase, TextToSpeechEntity):
    """Amazon Polly text-to-speech entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "tts"

    def __init__(self, entry: AmazonPollyConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data, entry.options)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Amazon",
            model="Polly",
            name=entry.title,
        )


class AmazonPollyProvider(AmazonPollyBase, Provider):
    """Legacy YAML Amazon Polly speech provider."""

    def __init__(self, data: AmazonPollyData, config: ConfigType) -> None:
        """Initialize the provider."""
        super().__init__(data, config)
        self.name = "Amazon Polly"
