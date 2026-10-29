"""Test wake word audio from satellites in Assist pipelines."""

from collections.abc import AsyncGenerator, AsyncIterable

import pytest

from homeassistant.components import assist_pipeline, stt, wake_word
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.assist_pipeline.const import BYTES_PER_CHUNK, MS_PER_CHUNK
from homeassistant.core import Context, HomeAssistant

from .conftest import MockSTTProviderEntity, make_10ms_chunk

WAKE = make_10ms_chunk(b"wake")
WORD = make_10ms_chunk(b"word")
COMMAND = make_10ms_chunk(b"command")


async def _audio_stream(*chunks: bytes) -> AsyncGenerator[bytes]:
    for chunk in chunks:
        yield chunk


async def _async_run_pipeline(
    hass: HomeAssistant, audio_stream: AsyncIterable[bytes], timestamp: int
) -> list[PipelineEvent]:
    events: list[PipelineEvent] = []
    await assist_pipeline.async_pipeline_from_audio_stream(
        hass,
        context=Context(),
        event_callback=events.append,
        stt_metadata=stt.SpeechMetadata(
            language="",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        stt_stream=audio_stream,
        wake_word_phrase="okay nabu",
        wake_word_detection=wake_word.DetectionResult(
            wake_word_id="okay_nabu",
            wake_word_phrase="okay nabu",
            timestamp=timestamp,
        ),
        audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
        end_stage=assist_pipeline.PipelineStage.STT,
    )
    return events


@pytest.mark.usefixtures("init_components")
async def test_wake_word_audio(
    hass: HomeAssistant,
    mock_stt_provider_entity: MockSTTProviderEntity,
) -> None:
    """Test the wake word is accepted and its audio removed for speech-to-text."""
    # Ends within a chunk
    timestamp = MS_PER_CHUNK + (MS_PER_CHUNK // 2)
    audio = [WAKE, WORD, COMMAND, bytes(BYTES_PER_CHUNK // 2)]
    events = await _async_run_pipeline(hass, _audio_stream(*audio), timestamp)

    assert [event.type for event in events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.WAKE_WORD_END,
        PipelineEventType.STT_START,
        PipelineEventType.STT_END,
        PipelineEventType.RUN_END,
    ]
    assert events[1].data == {
        "wake_word_output": {
            "wake_word_id": "okay_nabu",
            "wake_word_phrase": "okay nabu",
            "timestamp": timestamp,
        }
    }
    assert (
        b"".join(mock_stt_provider_entity.received)
        == b"".join(audio)[timestamp * BYTES_PER_CHUNK // MS_PER_CHUNK :]
    )


@pytest.mark.usefixtures("init_components", "mock_stt_provider_entity")
async def test_wake_word_audio_duplicate(hass: HomeAssistant) -> None:
    """Test a wake word another satellite just woke up with is rejected."""
    first_events = await _async_run_pipeline(
        hass, _audio_stream(WAKE, COMMAND), MS_PER_CHUNK
    )
    second_events = await _async_run_pipeline(
        hass, _audio_stream(WAKE, COMMAND), MS_PER_CHUNK
    )

    assert first_events[1].type is PipelineEventType.WAKE_WORD_END
    assert [event.type for event in second_events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.WAKE_WORD_REJECTED,
        PipelineEventType.RUN_END,
    ]
    assert second_events[1].data == {
        "wake_word_output": {
            "wake_word_id": "okay_nabu",
            "wake_word_phrase": "okay nabu",
            "timestamp": MS_PER_CHUNK,
        }
    }
