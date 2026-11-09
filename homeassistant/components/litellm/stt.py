"""Speech-to-text support for LiteLLM."""

from collections.abc import AsyncIterable
import io
from typing import override
import wave

from openai import (
    APIConnectionError,
    AuthenticationError,
    Omit,
    OpenAIError,
    PermissionDeniedError,
    omit,
)

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template

from .const import (
    CONF_STT_CUSTOM_PROMPT_KEYWORDS,
    CONF_STT_KEYWORDS,
    CONF_STT_PROMPT,
    LOGGER,
)
from .coordinator import LiteLLMConfigEntry
from .entity import LiteLLMEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LiteLLMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LiteLLM STT entities."""
    for subentry in config_entry.get_subentries_of_type("stt"):
        async_add_entities(
            [LiteLLMSTTEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LiteLLMSTTEntity(LiteLLMEntity, stt.SpeechToTextEntity):
    """LiteLLM speech-to-text entity."""

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return supported languages.

        LiteLLM does not expose model-specific language capabilities; the
        selected backend may reject the advertised language.
        """
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
    @override
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return supported formats.

        LiteLLM does not expose model-specific audio capabilities; the backend
        may reject this.
        """
        return [stt.AudioFormats.WAV]

    @property
    @override
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return supported codecs.

        LiteLLM does not expose model-specific audio capabilities; the backend
        may reject this.
        """
        return [stt.AudioCodecs.PCM]

    @property
    @override
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return supported bit rates.

        LiteLLM does not expose model-specific audio capabilities; the backend
        may reject this.
        """
        return [stt.AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return supported sample rates.

        LiteLLM does not expose model-specific audio capabilities; the backend
        may reject this.
        """
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return supported channels.

        LiteLLM does not expose model-specific audio capabilities; the backend
        may reject this.
        """
        return [stt.AudioChannels.CHANNEL_MONO]

    @override
    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process audio with the transcription endpoint."""
        audio_bytes = bytearray()
        async for chunk in stream:
            audio_bytes.extend(chunk)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(metadata.channel.value)
            wav_file.setsampwidth(metadata.bit_rate.value // 8)
            wav_file.setframerate(metadata.sample_rate.value)
            wav_file.writeframes(audio_bytes)

        coordinator = self.entry.runtime_data
        options = self.subentry.data

        try:
            prompt: str | Omit = omit
            keyword_list: list[str] | Omit = omit
            if options.get(CONF_STT_CUSTOM_PROMPT_KEYWORDS):
                if prompt_value := options.get(CONF_STT_PROMPT):
                    prompt = (
                        Template(prompt_value, self.hass).async_render(
                            parse_result=False
                        )
                        or omit
                    )

                if keywords_value := options.get(CONF_STT_KEYWORDS):
                    keywords = Template(keywords_value, self.hass).async_render(
                        parse_result=False
                    )
                    keyword_list = [
                        keyword.strip()
                        for keyword in keywords.split(",")
                        if keyword.strip()
                    ] or omit

            response = await coordinator.client.audio.transcriptions.create(
                model=self.model,
                file=("audio.wav", wav_buffer.getvalue()),
                language=metadata.language.split("-")[0],
                prompt=prompt,
                keywords=keyword_list,
            )
        except TemplateError as err:
            LOGGER.error("Error rendering STT template: %s", err)
        except (AuthenticationError, PermissionDeniedError) as err:
            await coordinator.async_request_refresh()
            LOGGER.error("Authentication error during STT: %s", err)
        except APIConnectionError as err:
            coordinator.mark_connection_error()
            LOGGER.error("Connection error during STT: %s", err)
        except OpenAIError as err:
            coordinator.async_set_updated_data(None)
            LOGGER.error("Error during STT: %s", err)
        else:
            coordinator.async_set_updated_data(None)
            if response.text:
                return stt.SpeechResult(response.text, stt.SpeechResultState.SUCCESS)

        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
