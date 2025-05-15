"""Support for the cloud for text-to-speech service."""

from __future__ import annotations

import logging
from typing import Any

from hass_nabucasa import Cloud
from hass_nabucasa.voice import MAP_VOICE, AudioOutput, Gender, VoiceError
from hass_nabucasa.voice_data import TTS_VOICES
import voluptuous as vol

from homeassistant.components.tts import (
    ATTR_AUDIO_OUTPUT,
    ATTR_VOICE,
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant, async_get_hass, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_when_setup

from .assist_pipeline import async_migrate_cloud_pipeline_engine
from .client import CloudClient
from .const import (
    DATA_CLOUD,
    DATA_PLATFORMS_SETUP,
    DOMAIN,
    TTS_ENTITY_UNIQUE_ID,
    VOICE_STYLE_SEPERATOR,
)
from .prefs import CloudPreferences

ATTR_GENDER = "gender"

DEPRECATED_VOICES = {"XiaoxuanNeural": "XiaozhenNeural"}
SUPPORT_LANGUAGES = list(TTS_VOICES)

DEFAULT_VOICES = {
    "af-ZA": "AdriNeural",
    "am-ET": "MekdesNeural",
    "ar-AE": "FatimaNeural",
    "ar-BH": "LailaNeural",
    "ar-DZ": "AminaNeural",
    "ar-EG": "SalmaNeural",
    "ar-IQ": "RanaNeural",
    "ar-JO": "SanaNeural",
    "ar-KW": "NouraNeural",
    "ar-LB": "LaylaNeural",
    "ar-LY": "ImanNeural",
    "ar-MA": "MounaNeural",
    "ar-OM": "AbdullahNeural",
    "ar-QA": "AmalNeural",
    "ar-SA": "ZariyahNeural",
    "ar-SY": "AmanyNeural",
    "ar-TN": "ReemNeural",
    "ar-YE": "MaryamNeural",
    "as-IN": "PriyomNeural",
    "az-AZ": "BabekNeural",
    "bg-BG": "KalinaNeural",
    "bn-BD": "NabanitaNeural",
    "bn-IN": "TanishaaNeural",
    "bs-BA": "GoranNeural",
    "ca-ES": "JoanaNeural",
    "cs-CZ": "VlastaNeural",
    "cy-GB": "NiaNeural",
    "da-DK": "ChristelNeural",
    "de-AT": "IngridNeural",
    "de-CH": "LeniNeural",
    "de-DE": "KatjaNeural",
    "el-GR": "AthinaNeural",
    "en-AU": "NatashaNeural",
    "en-CA": "ClaraNeural",
    "en-GB": "LibbyNeural",
    "en-HK": "YanNeural",
    "en-IE": "EmilyNeural",
    "en-IN": "NeerjaNeural",
    "en-KE": "AsiliaNeural",
    "en-NG": "EzinneNeural",
    "en-NZ": "MollyNeural",
    "en-PH": "RosaNeural",
    "en-SG": "LunaNeural",
    "en-TZ": "ImaniNeural",
    "en-US": "JennyNeural",
    "en-ZA": "LeahNeural",
    "es-AR": "ElenaNeural",
    "es-BO": "SofiaNeural",
    "es-CL": "CatalinaNeural",
    "es-CO": "SalomeNeural",
    "es-CR": "MariaNeural",
    "es-CU": "BelkysNeural",
    "es-DO": "RamonaNeural",
    "es-EC": "AndreaNeural",
    "es-ES": "ElviraNeural",
    "es-GQ": "TeresaNeural",
    "es-GT": "MartaNeural",
    "es-HN": "KarlaNeural",
    "es-MX": "DaliaNeural",
    "es-NI": "YolandaNeural",
    "es-PA": "MargaritaNeural",
    "es-PE": "CamilaNeural",
    "es-PR": "KarinaNeural",
    "es-PY": "TaniaNeural",
    "es-SV": "LorenaNeural",
    "es-US": "PalomaNeural",
    "es-UY": "ValentinaNeural",
    "es-VE": "PaolaNeural",
    "et-EE": "AnuNeural",
    "eu-ES": "AinhoaNeural",
    "fa-IR": "DilaraNeural",
    "fi-FI": "SelmaNeural",
    "fil-PH": "BlessicaNeural",
    "fr-BE": "CharlineNeural",
    "fr-CA": "SylvieNeural",
    "fr-CH": "ArianeNeural",
    "fr-FR": "DeniseNeural",
    "ga-IE": "OrlaNeural",
    "gl-ES": "SabelaNeural",
    "gu-IN": "DhwaniNeural",
    "he-IL": "HilaNeural",
    "hi-IN": "SwaraNeural",
    "hr-HR": "GabrijelaNeural",
    "hu-HU": "NoemiNeural",
    "hy-AM": "AnahitNeural",
    "id-ID": "GadisNeural",
    "is-IS": "GudrunNeural",
    "it-IT": "ElsaNeural",
    "iu-Cans-CA": "SiqiniqNeural",
    "iu-Latn-CA": "SiqiniqNeural",
    "ja-JP": "NanamiNeural",
    "jv-ID": "SitiNeural",
    "ka-GE": "EkaNeural",
    "kk-KZ": "AigulNeural",
    "km-KH": "SreymomNeural",
    "kn-IN": "SapnaNeural",
    "ko-KR": "SunHiNeural",
    "lo-LA": "KeomanyNeural",
    "lt-LT": "OnaNeural",
    "lv-LV": "EveritaNeural",
    "mk-MK": "MarijaNeural",
    "ml-IN": "SobhanaNeural",
    "mn-MN": "BataaNeural",
    "mr-IN": "AarohiNeural",
    "ms-MY": "YasminNeural",
    "mt-MT": "GraceNeural",
    "my-MM": "NilarNeural",
    "nb-NO": "IselinNeural",
    "ne-NP": "HemkalaNeural",
    "nl-BE": "DenaNeural",
    "nl-NL": "ColetteNeural",
    "or-IN": "SubhasiniNeural",
    "pa-IN": "OjasNeural",
    "pl-PL": "AgnieszkaNeural",
    "ps-AF": "LatifaNeural",
    "pt-BR": "FranciscaNeural",
    "pt-PT": "RaquelNeural",
    "ro-RO": "AlinaNeural",
    "ru-RU": "SvetlanaNeural",
    "si-LK": "ThiliniNeural",
    "sk-SK": "ViktoriaNeural",
    "sl-SI": "PetraNeural",
    "so-SO": "UbaxNeural",
    "sq-AL": "AnilaNeural",
    "sr-Latn-RS": "NicholasNeural",
    "sr-RS": "SophieNeural",
    "su-ID": "TutiNeural",
    "sv-SE": "SofieNeural",
    "sw-KE": "ZuriNeural",
    "sw-TZ": "RehemaNeural",
    "ta-IN": "PallaviNeural",
    "ta-LK": "SaranyaNeural",
    "ta-MY": "KaniNeural",
    "ta-SG": "VenbaNeural",
    "te-IN": "ShrutiNeural",
    "th-TH": "AcharaNeural",
    "tr-TR": "EmelNeural",
    "uk-UA": "PolinaNeural",
    "ur-IN": "GulNeural",
    "ur-PK": "UzmaNeural",
    "uz-UZ": "MadinaNeural",
    "vi-VN": "HoaiMyNeural",
    "wuu-CN": "XiaotongNeural",
    "yue-CN": "XiaoMinNeural",
    "zh-CN-henan": "YundengNeural",
    "zh-CN-shandong": "YunxiangNeural",
    "zh-CN": "XiaoxiaoNeural",
    "zh-HK": "HiuMaanNeural",
    "zh-TW": "HsiaoChenNeural",
    "zu-ZA": "ThandoNeural",
}

_LOGGER = logging.getLogger(__name__)


@callback
def _prepare_voice_args(
    *,
    hass: HomeAssistant,
    language: str,
    voice: str,
    gender: str | None,
) -> dict:
    """Prepare voice arguments."""
    gender = handle_deprecated_gender(hass, gender)
    style: str | None
    original_voice, _, style = voice.partition(VOICE_STYLE_SEPERATOR)
    if not style:
        style = None
    updated_voice = handle_deprecated_voice(hass, original_voice)
    if updated_voice not in TTS_VOICES[language]:
        default_voice = DEFAULT_VOICES[language]
        _LOGGER.debug(
            "Unsupported voice %s detected, falling back to default %s for %s",
            voice,
            default_voice,
            language,
        )
        updated_voice = default_voice

    return {
        "language": language,
        "voice": updated_voice,
        "gender": gender,
        "style": style,
    }


def _deprecated_platform(value: str) -> str:
    """Validate if platform is deprecated."""
    if value == DOMAIN:
        _LOGGER.warning(
            "The cloud tts platform configuration is deprecated, "
            "please remove it from your configuration "
            "and use the UI to change settings instead"
        )
        hass = async_get_hass()
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_tts_platform_config",
            breaks_in_ha_version="2024.9.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_tts_platform_config",
        )
    return value


def validate_lang(value: dict[str, Any]) -> dict[str, Any]:
    """Validate chosen gender or language."""
    if (lang := value.get(CONF_LANG)) is None:
        return value

    if (gender := value.get(ATTR_GENDER)) is None:
        gender = value[ATTR_GENDER] = next(
            (chk_gender for chk_lang, chk_gender in MAP_VOICE if chk_lang == lang), None
        )

    if (lang, gender) not in MAP_VOICE:
        raise vol.Invalid("Unsupported language and gender specified.")

    return value


PLATFORM_SCHEMA = vol.All(
    TTS_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): vol.All(cv.string, _deprecated_platform),
            vol.Optional(CONF_LANG): str,
            vol.Optional(ATTR_GENDER): str,
        }
    ),
    validate_lang,
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CloudProvider:
    """Set up Cloud speech component."""
    cloud = hass.data[DATA_CLOUD]
    cloud_provider = CloudProvider(cloud)
    if discovery_info is not None:
        discovery_info["platform_loaded"].set()
    return cloud_provider


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud text-to-speech platform."""
    tts_platform_loaded = hass.data[DATA_PLATFORMS_SETUP][Platform.TTS]
    tts_platform_loaded.set()
    cloud = hass.data[DATA_CLOUD]
    async_add_entities([CloudTTSEntity(cloud)])


class CloudTTSEntity(TextToSpeechEntity):
    """Home Assistant Cloud text-to-speech entity."""

    _attr_name = "Home Assistant Cloud"
    _attr_unique_id = TTS_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize cloud text-to-speech entity."""
        self.cloud = cloud
        self._language, self._voice = cloud.client.prefs.tts_default_voice

    async def _sync_prefs(self, prefs: CloudPreferences) -> None:
        """Sync preferences."""
        self._language, self._voice = prefs.tts_default_voice

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._language

    @property
    def default_options(self) -> dict[str, str]:
        """Return a dict include default options."""
        return {
            ATTR_AUDIO_OUTPUT: AudioOutput.MP3,
        }

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotion."""
        # The gender option is deprecated and will be removed in 2024.10.0.
        return [ATTR_GENDER, ATTR_VOICE, ATTR_AUDIO_OUTPUT]

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        async def pipeline_setup(hass: HomeAssistant, _comp: str) -> None:
            """When assist_pipeline is set up."""
            assert self.platform.config_entry
            self.platform.config_entry.async_create_task(
                hass,
                async_migrate_cloud_pipeline_engine(
                    self.hass, platform=Platform.TTS, engine_id=self.entity_id
                ),
            )

        async_when_setup(self.hass, "assist_pipeline", pipeline_setup)

        self.async_on_remove(
            self.cloud.client.prefs.async_listen_updates(self._sync_prefs)
        )

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := TTS_VOICES.get(language)):
            return None

        result = []

        for voice_id, voice_info in voices.items():
            if isinstance(voice_info, str):
                result.append(
                    Voice(
                        voice_id,
                        voice_info,
                    )
                )
                continue

            name = voice_info["name"]

            result.append(
                Voice(
                    voice_id,
                    name,
                )
            )
            result.extend(
                [
                    Voice(
                        f"{voice_id}{VOICE_STYLE_SEPERATOR}{variant}",
                        f"{name} ({variant})",
                    )
                    for variant in voice_info.get("variants", [])
                ]
            )

        return result

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Home Assistant Cloud."""
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                text=message,
                output=options[ATTR_AUDIO_OUTPUT],
                **_prepare_voice_args(
                    hass=self.hass,
                    language=language,
                    voice=options.get(
                        ATTR_VOICE,
                        (
                            self._voice
                            if language == self._language
                            else DEFAULT_VOICES[language]
                        ),
                    ),
                    gender=options.get(ATTR_GENDER),
                ),
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return (None, None)

        return (options[ATTR_AUDIO_OUTPUT], data)


class CloudProvider(Provider):
    """Home Assistant Cloud speech API provider."""

    has_entity = True

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize cloud provider."""
        self.cloud = cloud
        self.name = "Home Assistant Cloud"
        self._language, self._voice = cloud.client.prefs.tts_default_voice
        cloud.client.prefs.async_listen_updates(self._sync_prefs)

    async def _sync_prefs(self, prefs: CloudPreferences) -> None:
        """Sync preferences."""
        self._language, self._voice = prefs.tts_default_voice

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotion."""
        # The gender option is deprecated and will be removed in 2024.10.0.
        return [ATTR_GENDER, ATTR_VOICE, ATTR_AUDIO_OUTPUT]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := TTS_VOICES.get(language)):
            return None

        result = []

        for voice_id, voice_info in voices.items():
            if isinstance(voice_info, str):
                result.append(
                    Voice(
                        voice_id,
                        voice_info,
                    )
                )
                continue

            name = voice_info["name"]

            result.append(
                Voice(
                    voice_id,
                    name,
                )
            )
            result.extend(
                [
                    Voice(
                        f"{voice_id}{VOICE_STYLE_SEPERATOR}{variant}",
                        f"{name} ({variant})",
                    )
                    for variant in voice_info.get("variants", [])
                ]
            )

        return result

    @property
    def default_options(self) -> dict[str, str]:
        """Return a dict include default options."""
        return {
            ATTR_AUDIO_OUTPUT: AudioOutput.MP3,
        }

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Home Assistant Cloud."""
        assert self.hass is not None
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                text=message,
                output=options[ATTR_AUDIO_OUTPUT],
                **_prepare_voice_args(
                    hass=self.hass,
                    language=language,
                    voice=options.get(
                        ATTR_VOICE,
                        self._voice
                        if language == self._language
                        else DEFAULT_VOICES[language],
                    ),
                    gender=options.get(ATTR_GENDER),
                ),
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return (None, None)

        return options[ATTR_AUDIO_OUTPUT], data


@callback
def handle_deprecated_gender(
    hass: HomeAssistant,
    gender: Gender | str | None,
) -> Gender | None:
    """Handle deprecated gender."""
    if gender is None:
        return None
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_gender",
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        breaks_in_ha_version="2024.10.0",
        translation_key="deprecated_gender",
        translation_placeholders={
            "integration_name": "Home Assistant Cloud",
            "deprecated_option": "gender",
            "replacement_option": "voice",
        },
    )
    return Gender(gender)


@callback
def handle_deprecated_voice(
    hass: HomeAssistant,
    original_voice: str | None,
) -> str | None:
    """Handle deprecated voice."""
    voice = original_voice
    if (
        original_voice
        and voice
        and (voice := DEPRECATED_VOICES.get(original_voice, original_voice))
        != original_voice
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_voice_{original_voice}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            breaks_in_ha_version="2024.8.0",
            translation_key="deprecated_voice",
            translation_placeholders={
                "deprecated_voice": original_voice,
                "replacement_voice": voice,
            },
        )
    return voice
