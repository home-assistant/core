"""Speech-to-text support for Mistral AI."""

from collections.abc import AsyncIterable
import io
import logging
from typing import TYPE_CHECKING, override
import wave

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL
from .entity import MistralEntity

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_LANGUAGES = [
    "af",
    "am",
    "ar",
    "as",
    "az",
    "ba",
    "be",
    "bg",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fo",  # codespell:ignore fo
    "fr",
    "gl",
    "gu",
    "ha",
    "haw",
    "he",
    "hi",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "la",
    "lb",
    "ln",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "nn",
    "no",
    "oc",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sa",
    "sd",
    "si",
    "sk",
    "sl",
    "sn",
    "so",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",  # codespell:ignore te
    "tg",
    "th",
    "tk",
    "tl",
    "tr",
    "tt",
    "uk",
    "ur",
    "uz",
    "vi",
    "yi",
    "yo",
    "yue",
    "zh",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral STT platform."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stt":
            continue

        async_add_entities(
            [MistralSTTEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralSTTEntity(stt.SpeechToTextEntity, MistralEntity):
    """Mistral AI speech-to-text entity."""

    @property
    @override
    def supported_languages(self) -> list[str]:
        return _LANGUAGES

    @property
    @override
    def supported_formats(self) -> list[stt.AudioFormats]:
        return [stt.AudioFormats.WAV]

    @property
    @override
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        return [stt.AudioCodecs.PCM]

    @property
    @override
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        return [stt.AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[stt.AudioChannels]:
        return [stt.AudioChannels.CHANNEL_MONO]

    @override
    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        audio_bytes = bytearray()
        async for chunk in stream:
            audio_bytes.extend(chunk)
        audio_data = bytes(audio_bytes)

        if metadata.format == stt.AudioFormats.WAV:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(metadata.channel.value)
                wf.setsampwidth(metadata.bit_rate.value // 8)
                wf.setframerate(metadata.sample_rate.value)
                wf.writeframes(audio_data)
            audio_data = wav_buffer.getvalue()

        options = self.subentry.data
        client = self.entry.runtime_data.client

        try:
            response = await client.audio.transcriptions.complete_async(
                model=options.get(CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL),
                file={
                    "file_name": "audio.wav",
                    "content": audio_data,
                    "content_type": "audio/wav",
                },
                language=metadata.language.split("-")[0],
            )
        except Exception:
            _LOGGER.exception("Error during STT")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
        return stt.SpeechResult(response.text, stt.SpeechResultState.SUCCESS)
