"""Speech to text support for OpenAI."""

from __future__ import annotations

from collections.abc import AsyncIterable
import io
import logging
from typing import TYPE_CHECKING
import wave

from openai import OpenAIError

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DEFAULT_STT_PROMPT,
    RECOMMENDED_STT_MODEL,
)
from .entity import OpenAIBaseLLMEntity

if TYPE_CHECKING:
    from . import OpenAIConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stt":
            continue

        async_add_entities(
            [OpenAISTTEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenAISTTEntity(stt.SpeechToTextEntity, OpenAIBaseLLMEntity):
    """OpenAI Speech to text entity."""

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        # https://developers.openai.com/api/docs/guides/speech-to-text#supported-languages
        # The model may also transcribe the audio in other languages but with lower quality
        return [
            "af-ZA",  # Afrikaans
            "ar-SA",  # Arabic
            "hy-AM",  # Armenian
            "az-AZ",  # Azerbaijani
            "be-BY",  # Belarusian
            "bs-BA",  # Bosnian
            "bg-BG",  # Bulgarian
            "ca-ES",  # Catalan
            "zh-CN",  # Chinese (Mandarin)
            "hr-HR",  # Croatian
            "cs-CZ",  # Czech
            "da-DK",  # Danish
            "nl-NL",  # Dutch
            "en-US",  # English
            "et-EE",  # Estonian
            "fi-FI",  # Finnish
            "fr-FR",  # French
            "gl-ES",  # Galician
            "de-DE",  # German
            "el-GR",  # Greek
            "he-IL",  # Hebrew
            "hi-IN",  # Hindi
            "hu-HU",  # Hungarian
            "is-IS",  # Icelandic
            "id-ID",  # Indonesian
            "it-IT",  # Italian
            "ja-JP",  # Japanese
            "kn-IN",  # Kannada
            "kk-KZ",  # Kazakh
            "ko-KR",  # Korean
            "lv-LV",  # Latvian
            "lt-LT",  # Lithuanian
            "mk-MK",  # Macedonian
            "ms-MY",  # Malay
            "mr-IN",  # Marathi
            "mi-NZ",  # Maori
            "ne-NP",  # Nepali
            "no-NO",  # Norwegian
            "fa-IR",  # Persian
            "pl-PL",  # Polish
            "pt-PT",  # Portuguese
            "ro-RO",  # Romanian
            "ru-RU",  # Russian
            "sr-RS",  # Serbian
            "sk-SK",  # Slovak
            "sl-SI",  # Slovenian
            "es-ES",  # Spanish
            "sw-KE",  # Swahili
            "sv-SE",  # Swedish
            "fil-PH",  # Tagalog (Filipino)
            "ta-IN",  # Tamil
            "th-TH",  # Thai
            "tr-TR",  # Turkish
            "uk-UA",  # Ukrainian
            "ur-PK",  # Urdu
            "vi-VN",  # Vietnamese
            "cy-GB",  # Welsh
        ]

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        # https://developers.openai.com/api/docs/guides/speech-to-text#transcriptions
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [
            stt.AudioBitRates.BITRATE_8,
            stt.AudioBitRates.BITRATE_16,
            stt.AudioBitRates.BITRATE_24,
            stt.AudioBitRates.BITRATE_32,
        ]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [
            stt.AudioSampleRates.SAMPLERATE_8000,
            stt.AudioSampleRates.SAMPLERATE_11000,
            stt.AudioSampleRates.SAMPLERATE_16000,
            stt.AudioSampleRates.SAMPLERATE_18900,
            stt.AudioSampleRates.SAMPLERATE_22000,
            stt.AudioSampleRates.SAMPLERATE_32000,
            stt.AudioSampleRates.SAMPLERATE_37800,
            stt.AudioSampleRates.SAMPLERATE_44100,
            stt.AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO, stt.AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream to STT service."""
        audio_bytes = bytearray()
        async for chunk in stream:
            audio_bytes.extend(chunk)
        audio_data = bytes(audio_bytes)
        if metadata.format == stt.AudioFormats.WAV:
            # Add missing wav header
            wav_buffer = io.BytesIO()

            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(metadata.channel.value)
                wf.setsampwidth(metadata.bit_rate.value // 8)
                wf.setframerate(metadata.sample_rate.value)
                wf.writeframes(audio_data)

            audio_data = wav_buffer.getvalue()

        options = self.subentry.data
        client = self.entry.runtime_data

        try:
            response = await client.audio.transcriptions.create(
                model=options.get(CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL),
                file=(f"a.{metadata.format.value}", audio_data),
                response_format="json",
                language=metadata.language.split("-")[0],
                prompt=options.get(CONF_PROMPT, DEFAULT_STT_PROMPT),
            )
        except OpenAIError:
            _LOGGER.exception("Error during STT")
        else:
            if response.text:
                return stt.SpeechResult(
                    response.text,
                    stt.SpeechResultState.SUCCESS,
                )

        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
