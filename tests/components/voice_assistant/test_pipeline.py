"""Pipeline tests for Voice Assistant integration."""
from collections.abc import AsyncIterable
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import stt
from homeassistant.components.voice_assistant.pipeline import (
    AudioPipelineRequest,
    Pipeline,
    PipelineEventType,
    PipelineRun,
)
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    mock_get_cache_files,
    mock_init_cache_dir,
)


class MockSttProvider(stt.Provider):
    """Mock STT provider."""

    def __init__(self) -> None:
        """Init test provider."""
        self.calls = []

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return ["en"]

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bitrates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream."""
        self.calls.append((metadata, stream))
        return stt.SpeechResult("test stt transcript", stt.SpeechResultState.SUCCESS)


@pytest.fixture(autouse=True)
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "media_source", {})
    assert await async_setup_component(
        hass,
        "tts",
        {
            "tts": {
                "platform": "demo",
            }
        },
    )
    assert await async_setup_component(hass, "stt", {})

    # mock_platform fails because it can't import
    hass.data[stt.DOMAIN] = {"test": MockSttProvider()}

    assert await async_setup_component(hass, "voice_assistant", {})

    with patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=("mp3", b""),
    ) as mock_get_tts:
        yield mock_get_tts


async def test_audio_pipeline(hass):
    """Run audio pipeline with mock TTS."""
    pipeline = Pipeline(
        name="test",
        language=hass.config.language,
        stt_engine=None,
        conversation_engine=None,
        tts_engine=None,
    )

    async def stt_stream():
        while True:
            yield bytes(1)

    event_callback = MagicMock()
    stt_metadata = stt.SpeechMetadata(
        language=hass.config.language,
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    await AudioPipelineRequest(stt_metadata, stt_stream()).execute(
        PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            event_callback=event_callback,
            language=hass.config.language,
        )
    )

    calls = event_callback.mock_calls
    assert calls[0].args[0].type == PipelineEventType.RUN_START
    assert calls[0].args[0].data == {
        "pipeline": "test",
        "language": hass.config.language,
    }

    # Speech to text
    assert calls[1].args[0].type == PipelineEventType.STT_START
    assert calls[1].args[0].data == {
        "engine": "default",
    }
    assert calls[2].args[0].type == PipelineEventType.STT_FINISH

    # Intent recognition
    assert calls[3].args[0].type == PipelineEventType.INTENT_START
    assert calls[3].args[0].data == {
        "engine": "default",
        "intent_input": "test stt transcript",
    }
    assert calls[4].args[0].type == PipelineEventType.INTENT_FINISH
    assert calls[4].args[0].data == {
        "intent_output": {
            "conversation_id": None,
            "response": {
                "card": {},
                "data": {"code": "no_intent_match"},
                "language": hass.config.language,
                "response_type": "error",
                "speech": {
                    "plain": {
                        "extra_data": None,
                        "speech": "Sorry, I couldn't understand that",
                    }
                },
            },
        }
    }

    # Text to speech
    assert calls[5].args[0].type == PipelineEventType.TTS_START
    assert calls[5].args[0].data == {
        "engine": "default",
        "tts_input": "Sorry, I couldn't understand that",
    }
    assert calls[6].args[0].type == PipelineEventType.TTS_FINISH
    assert (
        calls[6].args[0].data["tts_output"]
        == f"/api/tts_proxy/dae2cdcb27a1d1c3b07ba2c7db91480f9d4bfd8f_{hass.config.language}_-_demo.mp3"
    )

    assert calls[7].args[0].type == PipelineEventType.RUN_FINISH
