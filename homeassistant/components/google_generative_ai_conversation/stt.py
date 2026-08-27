"""Speech to text support for Google Generative AI."""

from collections.abc import AsyncIterable
import io
from typing import cast, override

from google.genai.errors import APIError, ClientError
from google.genai.interactions import (
    AudioContentMimeType,
    AudioContentParam,
    TranscriptionConfigParam,
)
from google.genai.types import Part

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CHAT_MODEL, DEFAULT_STT_PROMPT, LOGGER, RECOMMENDED_STT_MODEL
from .entity import GoogleGenerativeAILLMBaseEntity
from .helpers import convert_to_wav


def _model_requires_interactions_api(model: str) -> bool:
    """Return whether a model is only reachable through the Interactions API.

    Neither the SDK nor Google's model listing API documents a way to
    detect this from the model itself, so this is a name-based heuristic
    matched as a substring (not just a suffix) so dated/preview variants
    like "gemini-3.5-transcribe-preview" are covered too.
    """
    return "-transcribe" in model.rsplit("/", maxsplit=1)[-1]


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
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return [
            "af-ZA",
            "am-ET",
            "ar-AE",
            "ar-BH",
            "ar-DZ",
            "ar-EG",
            "ar-IL",
            "ar-IQ",
            "ar-JO",
            "ar-KW",
            "ar-LB",
            "ar-MA",
            "ar-OM",
            "ar-PS",
            "ar-QA",
            "ar-SA",
            "ar-TN",
            "ar-YE",
            "az-AZ",
            "bg-BG",
            "bn-BD",
            "bn-IN",
            "bs-BA",
            "ca-ES",
            "cs-CZ",
            "da-DK",
            "de-AT",
            "de-CH",
            "de-DE",
            "el-GR",
            "en-AU",
            "en-CA",
            "en-GB",
            "en-GH",
            "en-HK",
            "en-IE",
            "en-IN",
            "en-KE",
            "en-NG",
            "en-NZ",
            "en-PH",
            "en-PK",
            "en-SG",
            "en-TZ",
            "en-US",
            "en-ZA",
            "es-AR",
            "es-BO",
            "es-CL",
            "es-CO",
            "es-CR",
            "es-DO",
            "es-EC",
            "es-ES",
            "es-GT",
            "es-HN",
            "es-MX",
            "es-NI",
            "es-PA",
            "es-PE",
            "es-PR",
            "es-PY",
            "es-SV",
            "es-US",
            "es-UY",
            "es-VE",
            "et-EE",
            "eu-ES",
            "fa-IR",
            "fi-FI",
            "fil-PH",
            "fr-BE",
            "fr-CA",
            "fr-CH",
            "fr-FR",
            "ga-IE",
            "gl-ES",
            "gu-IN",
            "he-IL",
            "hi-IN",
            "hr-HR",
            "hu-HU",
            "hy-AM",
            "id-ID",
            "is-IS",
            "it-CH",
            "it-IT",
            "iw-IL",
            "ja-JP",
            "jv-ID",
            "ka-GE",
            "kk-KZ",
            "km-KH",
            "kn-IN",
            "ko-KR",
            "lb-LU",
            "lo-LA",
            "lt-LT",
            "lv-LV",
            "mk-MK",
            "ml-IN",
            "mn-MN",
            "mr-IN",
            "ms-MY",
            "my-MM",
            "nb-NO",
            "ne-NP",
            "nl-BE",
            "nl-NL",
            "no-NO",
            "pl-PL",
            "pt-BR",
            "pt-PT",
            "ro-RO",
            "ru-RU",
            "si-LK",
            "sk-SK",
            "sl-SI",
            "sq-AL",
            "sr-RS",
            "su-ID",
            "sv-SE",
            "sw-KE",
            "sw-TZ",
            "ta-IN",
            "ta-LK",
            "ta-MY",
            "ta-SG",
            "te-IN",
            "th-TH",
            "tr-TR",
            "uk-UA",
            "ur-IN",
            "ur-PK",
            "uz-UZ",
            "vi-VN",
            "zh-CN",
            "zh-HK",
            "zh-TW",
            "zu-ZA",
        ]

    @property
    @override
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        # https://ai.google.dev/gemini-api/docs/audio#supported-formats
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    @override
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    @override
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        # Per
        # https://ai.google.dev/gemini-api/docs/audio
        # If the audio source contains multiple channels,
        # Gemini combines those channels into a single channel.
        return [stt.AudioChannels.CHANNEL_MONO]

    @override
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

        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL)

        if _model_requires_interactions_api(model):
            return await self._async_transcribe_via_interactions(
                model, audio_data, metadata
            )

        prompt = self.subentry.data.get(CONF_PROMPT, DEFAULT_STT_PROMPT)
        if metadata.language:
            prompt = (
                f"{prompt}\n"
                f"The spoken language is {metadata.language}. "
                f"Transcribe in that language."
            )

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=model,
                contents=[
                    prompt,
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

    async def _async_transcribe_via_interactions(
        self,
        model: str,
        audio_data: bytes,
        metadata: stt.SpeechMetadata,
    ) -> stt.SpeechResult:
        """Transcribe audio through the Interactions API.

        Used for models only served this way (not generateContent), like
        gemini-3.5-transcribe. This API doesn't accept a system prompt or
        sampling/safety options, so those are skipped.
        """
        if self.subentry.data.get(CONF_PROMPT):
            LOGGER.debug("Ignoring configured STT prompt: not supported by %s", model)

        audio_content: AudioContentParam = {
            "type": "audio",
            "data": io.BytesIO(audio_data),
            "mime_type": cast(AudioContentMimeType, f"audio/{metadata.format.value}"),
        }
        transcription_config: TranscriptionConfigParam = {}
        if metadata.language:
            transcription_config["language_codes"] = [metadata.language]

        try:
            interaction = await self._genai_client.aio.interactions.create(
                model=model,
                store=False,
                stream=False,
                input=[audio_content],
                generation_config={"transcription_config": transcription_config},
            )
        except Exception as err:  # noqa: BLE001
            # This API has no public exception type to catch narrowly.
            LOGGER.error("Error during STT: %s", err)
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        # mypy can't narrow create()'s return type here (an SDK typing gap);
        # the streaming variant can't happen since stream=False.
        output_text = interaction.output_text  # type: ignore[union-attr]
        if output_text:
            return stt.SpeechResult(output_text, stt.SpeechResultState.SUCCESS)

        status = interaction.status  # type: ignore[union-attr]
        LOGGER.error("STT response contained no text (status=%s)", status)
        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
