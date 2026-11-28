"""Text to speech support for Google Generative AI."""

from collections.abc import Mapping
from typing import Any, override

from google.genai import types
from google.genai.errors import APIError, ClientError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_TEMPERATURE,
    LOGGER,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TTS_MODEL,
)
from .entity import (
    GoogleGenerativeAILLMBaseEntity,
    supports_custom_sampling,
    supports_speech_metadata,
)
from .helpers import convert_to_wav

ATTR_STYLE = "style"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [GoogleGenerativeAITextToSpeechEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAITextToSpeechEntity(
    TextToSpeechEntity, GoogleGenerativeAILLMBaseEntity
):
    """Google Generative AI text-to-speech entity."""

    # See https://ai.google.dev/gemini-api/docs/speech-generation#languages
    # Note the documentation might not be up to date, e.g. el-GR is not listed
    # there but is supported. The docs only name the languages, so regions are
    # the CLDR likely region, or the locale of the voices API for regional variants.
    _attr_supported_languages = [
        "ace-ID",
        "af-ZA",
        "ak-GH",
        "am-ET",
        "ar-001",
        "ar-EG",
        "as-IN",
        "awa-IN",
        "az-AZ",
        "azb-IR",
        "ba-RU",
        "ban-ID",
        "be-BY",
        "bem-ZM",
        "bg-BG",
        "bho-IN",
        "bjn-ID",
        "bn-BD",
        "bs-BA",
        "bug-ID",
        "ca-ES",
        "ceb-PH",
        "ckb-IQ",
        "cmn-CN",
        "crh-UA",
        "cs-CZ",
        "da-DK",
        "de-DE",
        "dyu-BF",
        "dz-BT",
        "el-GR",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IE",
        "en-IN",
        "en-NZ",
        "en-US",
        "en-ZA",
        "es-419",
        "es-ES",
        "es-US",
        "et-EE",
        "eu-ES",
        "fa-IR",
        "fi-FI",
        "fil-PH",
        "fr-CA",
        "fr-FR",
        "fuv-NG",
        "gl-ES",
        "gn-PY",
        "gu-IN",
        "ha-NG",
        "he-IL",
        "hi-IN",
        "hne-IN",
        "hr-HR",
        "ht-HT",
        "hu-HU",
        "hy-AM",
        "id-ID",
        "ig-NG",
        "ilo-PH",
        "is-IS",
        "it-IT",
        "ja-JP",
        "jv-ID",
        "ka-GE",
        "kab-DZ",
        "kam-KE",
        "kg-CD",
        "ki-KE",
        "kk-KZ",
        "km-KH",
        "kn-IN",
        "ko-KR",
        "kok-IN",
        "ks-IN",
        "ky-KG",
        "la-VA",
        "lb-LU",
        "lg-UG",
        "ln-CD",
        "lo-LA",
        "lt-LT",
        "ltg-LV",
        "lus-IN",
        "lv-LV",
        "mag-IN",
        "mai-IN",
        "mg-MG",
        "min-ID",
        "mk-MK",
        "ml-IN",
        "mn-MN",
        "mni-IN",
        "mr-IN",
        "ms-MY",
        "mt-MT",
        "my-MM",
        "nb-NO",
        "ne-NP",
        "nl-NL",
        "nn-NO",
        "nso-ZA",
        "ny-MW",
        "oc-FR",
        "or-IN",
        "pa-IN",
        "pag-PH",
        "pl-PL",
        "ps-AF",
        "pt-BR",
        "pt-PT",
        "ro-RO",
        "ru-RU",
        "rw-RW",
        "sat-IN",
        "sd-PK",
        "si-LK",
        "sk-SK",
        "sl-SI",
        "so-SO",
        "sq-AL",
        "sr-RS",
        "ss-ZA",
        "st-ZA",
        "sv-SE",
        "sw-KE",
        "ta-IN",
        "te-IN",
        "tg-TJ",
        "th-TH",
        "ti-ET",
        "tr-TR",
        "ug-CN",
        "uk-UA",
        "ur-PK",
        "uz-UZ",
        "vi-VN",
        "yue-HK",
        "zh-CN",
        "zh-TW",
    ]
    # Unused, but required by base class.
    # The Gemini TTS models detect the input language automatically.
    _attr_default_language = "en-US"
    # See https://ai.google.dev/gemini-api/docs/speech-generation#voices
    _supported_voices = [
        Voice(voice.split(" ", 1)[0].lower(), voice)
        for voice in (
            "Zephyr (Bright)",
            "Puck (Upbeat)",
            "Charon (Informative)",
            "Kore (Firm)",
            "Fenrir (Excitable)",
            "Leda (Youthful)",
            "Orus (Firm)",
            "Aoede (Breezy)",
            "Callirrhoe (Easy-going)",
            "Autonoe (Bright)",
            "Enceladus (Breathy)",
            "Iapetus (Clear)",
            "Umbriel (Easy-going)",
            "Algieba (Smooth)",
            "Despina (Smooth)",
            "Erinome (Clear)",
            "Algenib (Gravelly)",
            "Rasalgethi (Informative)",
            "Laomedeia (Upbeat)",
            "Achernar (Soft)",
            "Alnilam (Firm)",
            "Schedar (Even)",
            "Gacrux (Mature)",
            "Pulcherrima (Forward)",
            "Achird (Friendly)",
            "Zubenelgenubi (Casual)",
            "Vindemiatrix (Gentle)",
            "Sadachbia (Lively)",
            "Sadaltager (Knowledgeable)",
            "Sulafat (Warm)",
        )
    ]

    def __init__(self, config_entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        super().__init__(config_entry, subentry, RECOMMENDED_TTS_MODEL)

    @cached_property
    @override
    def supported_options(self) -> list[str]:
        """Return the options supported by the configured model."""
        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)
        if supports_speech_metadata(model):
            return [ATTR_VOICE, ATTR_STYLE]
        return [ATTR_VOICE]

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._supported_voices

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: self._supported_voices[0].voice_id,
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)
        config = types.GenerateContentConfig()
        if supports_custom_sampling(model):
            config.temperature = self.subentry.data.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            )
        config.response_modalities = ["AUDIO"]
        config.speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=options[ATTR_VOICE]
                )
            )
        )

        contents: str | types.Part = message
        if style := options.get(ATTR_STYLE):
            contents = types.Part(
                text=message,
                speech_metadata=types.SpeechMetadata(style=style),
            )

        def _extract_audio_parts(
            response: types.GenerateContentResponse,
        ) -> tuple[bytes, str]:
            if (
                not response.candidates
                or not response.candidates[0].content
                or not response.candidates[0].content.parts
                or not response.candidates[0].content.parts[0].inline_data
            ):
                raise ValueError("No content returned from TTS generation")

            data = response.candidates[0].content.parts[0].inline_data.data
            mime_type = response.candidates[0].content.parts[0].inline_data.mime_type

            if not isinstance(data, bytes):
                raise TypeError(
                    f"Expected bytes for audio data, got {type(data).__name__}"
                )
            if not isinstance(mime_type, str):
                raise TypeError(
                    f"Expected str for mime_type, got {type(mime_type).__name__}"
                )

            return data, mime_type

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            data, mime_type = _extract_audio_parts(response)
        except (APIError, ClientError, ValueError, TypeError) as exc:
            # pylint: disable-next=home-assistant-log-and-raise
            LOGGER.error("Error during TTS: %s", exc, exc_info=True)
            raise HomeAssistantError(exc) from exc
        if mime_type == "audio/wav":
            return "wav", data
        return "wav", convert_to_wav(data, mime_type)
