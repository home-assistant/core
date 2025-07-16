"""Speech to text support for Google Generative AI."""

from __future__ import annotations

from collections.abc import AsyncIterable

from google.genai.errors import APIError, ClientError
from google.genai.types import Part

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DEFAULT_STT_PROMPT,
    LOGGER,
    RECOMMENDED_STT_MODEL,
)
from .entity import GoogleGenerativeAILLMBaseEntity
from .helpers import convert_to_wav


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stt":
            continue

        async_add_entities(
            [GoogleGenerativeAISttEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAISttEntity(
    stt.SpeechToTextEntity, GoogleGenerativeAILLMBaseEntity
):
    """Google Generative AI speech-to-text entity."""

    def __init__(self, config_entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the STT entity."""
        super().__init__(config_entry, subentry, RECOMMENDED_STT_MODEL)

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return [
            "af-ZA",
            "sq-AL",
            "am-ET",
            "ar-DZ",
            "ar-BH",
            "ar-EG",
            "ar-IQ",
            "ar-IL",
            "ar-JO",
            "ar-KW",
            "ar-LB",
            "ar-MA",
            "ar-OM",
            "ar-QA",
            "ar-SA",
            "ar-PS",
            "ar-TN",
            "ar-AE",
            "ar-YE",
            "hy-AM",
            "az-AZ",
            "eu-ES",
            "bn-BD",
            "bn-IN",
            "bs-BA",
            "bg-BG",
            "my-MM",
            "ca-ES",
            "zh-CN",
            "zh-TW",
            "hr-HR",
            "cs-CZ",
            "da-DK",
            "nl-BE",
            "nl-NL",
            "en-AU",
            "en-CA",
            "en-GH",
            "en-HK",
            "en-IN",
            "en-IE",
            "en-KE",
            "en-NZ",
            "en-NG",
            "en-PK",
            "en-PH",
            "en-SG",
            "en-ZA",
            "en-TZ",
            "en-GB",
            "en-US",
            "et-EE",
            "fil-PH",
            "fi-FI",
            "fr-BE",
            "fr-CA",
            "fr-FR",
            "fr-CH",
            "gl-ES",
            "ka-GE",
            "de-AT",
            "de-DE",
            "de-CH",
            "el-GR",
            "gu-IN",
            "iw-IL",
            "hi-IN",
            "hu-HU",
            "is-IS",
            "id-ID",
            "it-IT",
            "it-CH",
            "ja-JP",
            "jv-ID",
            "kn-IN",
            "kk-KZ",
            "km-KH",
            "ko-KR",
            "lo-LA",
            "lv-LV",
            "lt-LT",
            "mk-MK",
            "ms-MY",
            "ml-IN",
            "mr-IN",
            "mn-MN",
            "ne-NP",
            "no-NO",
            "fa-IR",
            "pl-PL",
            "pt-BR",
            "pt-PT",
            "ro-RO",
            "ru-RU",
            "sr-RS",
            "si-LK",
            "sk-SK",
            "sl-SI",
            "es-AR",
            "es-BO",
            "es-CL",
            "es-CO",
            "es-CR",
            "es-DO",
            "es-EC",
            "es-SV",
            "es-GT",
            "es-HN",
            "es-MX",
            "es-NI",
            "es-PA",
            "es-PY",
            "es-PE",
            "es-PR",
            "es-ES",
            "es-US",
            "es-UY",
            "es-VE",
            "su-ID",
            "sw-KE",
            "sw-TZ",
            "sv-SE",
            "ta-IN",
            "ta-MY",
            "ta-SG",
            "ta-LK",
            "te-IN",
            "th-TH",
            "tr-TR",
            "uk-UA",
            "ur-IN",
            "ur-PK",
            "uz-UZ",
            "vi-VN",
            "zu-ZA",
        ]

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        # https://ai.google.dev/gemini-api/docs/audio#supported-formats
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        # Per https://ai.google.dev/gemini-api/docs/audio
        # If the audio source contains multiple channels, Gemini combines those channels into a single channel.
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream to STT service."""
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk
        if metadata.format == stt.AudioFormats.WAV:
            audio_data = convert_to_wav(
                audio_data,
                f"audio/L{metadata.bit_rate.value};rate={metadata.sample_rate.value}",
            )

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL),
                contents=[
                    self.subentry.data.get(CONF_PROMPT, DEFAULT_STT_PROMPT),
                    Part.from_bytes(
                        data=audio_data,
                        mime_type=f"audio/{metadata.format.value}",
                    ),
                ],
                config=self.create_generate_content_config(),
            )
        except (APIError, ClientError, ValueError) as err:
            LOGGER.error("Error during STT: %s", err)
        else:
            if response.text:
                return stt.SpeechResult(
                    response.text,
                    stt.SpeechResultState.SUCCESS,
                )

        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
