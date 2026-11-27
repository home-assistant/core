"""Support for the Microsoft Cognitive Services text-to-speech service."""

from enum import StrEnum
import logging
from typing import Any, override

import probatio
from pycsspeechtts import pycsspeechtts
from requests.exceptions import HTTPError, RequestException

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_REGION, CONF_TYPE, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.generated.microsoft_tts import SUPPORTED_LANGUAGES
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CONTOUR,
    CONF_GENDER,
    CONF_PITCH,
    CONF_RATE,
    CONF_VOLUME,
    DEFAULT_CONTOUR,
    DEFAULT_GENDER,
    DEFAULT_LANG,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_REGION,
    DEFAULT_TYPE,
    DEFAULT_VOLUME,
    DOMAIN,
    GENDERS,
    INTEGRATION_TITLE,
)
from .helpers import is_unauthorized

CONF_OUTPUT = "output"
_LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT = "audio-24khz-96kbitrate-mono-mp3"


class MicrosoftTextToSpeechOption(StrEnum):
    """Store keys for the Microsoft text-to-speech options."""

    GENDER = "gender"
    TYPE = "type"


PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Optional(CONF_LANG, default=DEFAULT_LANG): probatio.In(
            SUPPORTED_LANGUAGES
        ),
        probatio.Optional(
            CONF_GENDER, default=DEFAULT_GENDER.capitalize()
        ): probatio.In([gender.capitalize() for gender in GENDERS]),
        probatio.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
        probatio.Optional(CONF_RATE, default=DEFAULT_RATE): probatio.All(
            probatio.Coerce(int), probatio.Range(-100, 100)
        ),
        probatio.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): probatio.All(
            probatio.Coerce(int), probatio.Range(-100, 100)
        ),
        probatio.Optional(CONF_PITCH, default=DEFAULT_PITCH): cv.string,
        probatio.Optional(CONF_CONTOUR, default=DEFAULT_CONTOUR): cv.string,
        probatio.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
    }
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Provider:
    """Import the YAML configuration and set up the legacy engine."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    import_failed = (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    )
    issue_key = (
        f"deprecated_yaml_import_issue_{result['reason']}"
        if import_failed
        else "deprecated_yaml"
    )
    async_create_issue(
        hass,
        DOMAIN,
        issue_key,
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=issue_key,
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )

    return MicrosoftProvider(
        config[CONF_API_KEY],
        config[CONF_LANG],
        config[CONF_GENDER],
        config[CONF_TYPE],
        config[CONF_RATE],
        config[CONF_VOLUME],
        config[CONF_PITCH],
        config[CONF_CONTOUR],
        config[CONF_REGION],
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Microsoft text-to-speech entity."""
    async_add_entities([MicrosoftTTSEntity(entry)])


class MicrosoftTTSEntity(TextToSpeechEntity):
    """The Microsoft text-to-speech entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "text_to_speech"
    _attr_supported_languages = sorted(SUPPORTED_LANGUAGES)
    _attr_supported_options = [
        MicrosoftTextToSpeechOption.GENDER,
        MicrosoftTextToSpeechOption.TYPE,
    ]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._api_key: str = entry.data[CONF_API_KEY]
        self._region: str = entry.data[CONF_REGION]
        self._attr_default_language = entry.data[CONF_LANG]
        # The prosody settings are default options so that they are part of the
        # TTS cache key and changing them in the options flow invalidates the cache
        self._attr_default_options = {
            MicrosoftTextToSpeechOption.GENDER: entry.data[CONF_GENDER],
            MicrosoftTextToSpeechOption.TYPE: entry.data[CONF_TYPE],
            CONF_RATE: entry.options[CONF_RATE],
            CONF_VOLUME: entry.options[CONF_VOLUME],
            CONF_PITCH: entry.options[CONF_PITCH],
            CONF_CONTOUR: entry.options[CONF_CONTOUR],
        }
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Microsoft",
            model="Azure AI Speech",
            name="Microsoft",
        )

    @override
    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Microsoft."""
        try:
            translator = pycsspeechtts.TTSTranslator(self._api_key, self._region)
            data = translator.speak(
                language=language,
                gender=options[MicrosoftTextToSpeechOption.GENDER].capitalize(),
                voiceType=options[MicrosoftTextToSpeechOption.TYPE],
                output=DEFAULT_OUTPUT,
                rate=f"{options[CONF_RATE]}{PERCENTAGE}",
                volume=f"{options[CONF_VOLUME]}{PERCENTAGE}",
                pitch=options[CONF_PITCH],
                contour=options[CONF_CONTOUR],
                text=message,
            )
        except RequestException as err:
            if is_unauthorized(err):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="invalid_api_key"
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        if data is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="synthesis_failed"
            )
        return "mp3", data


class MicrosoftProvider(Provider):
    """The Microsoft speech API provider."""

    def __init__(
        self, apikey, lang, gender, ttype, rate, volume, pitch, contour, region
    ) -> None:
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._lang = lang
        self._gender = gender
        self._type = ttype
        self._output = DEFAULT_OUTPUT
        self._rate = f"{rate}{PERCENTAGE}"
        self._volume = f"{volume}{PERCENTAGE}"
        self._pitch = pitch
        self._contour = contour
        self._region = region
        self.name = "Microsoft"

    @property
    @override
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return list(SUPPORTED_LANGUAGES)

    @property
    @override
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotion."""
        return [MicrosoftTextToSpeechOption.GENDER, MicrosoftTextToSpeechOption.TYPE]

    @property
    @override
    def default_options(self) -> dict[str, Any]:
        """Return a dict include default options."""
        return {
            MicrosoftTextToSpeechOption.GENDER: self._gender,
            MicrosoftTextToSpeechOption.TYPE: self._type,
        }

    @override
    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Microsoft."""
        if language is None:
            language = self._lang

        try:
            trans = pycsspeechtts.TTSTranslator(self._apikey, self._region)
            data = trans.speak(
                language=language,
                gender=options[MicrosoftTextToSpeechOption.GENDER],
                voiceType=options[MicrosoftTextToSpeechOption.TYPE],
                output=self._output,
                rate=self._rate,
                volume=self._volume,
                pitch=self._pitch,
                contour=self._contour,
                text=message,
            )
        except HTTPError as ex:
            _LOGGER.error("Error occurred for Microsoft TTS: %s", ex)
            return (None, None)
        return ("mp3", data)
