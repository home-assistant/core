"""Test Voice Assistant init."""
from dataclasses import asdict
import itertools as it
from pathlib import Path
import tempfile
from unittest.mock import ANY, patch
import wave

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import assist_pipeline, stt
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockSttProvider, MockSttProviderEntity, MockWakeWordEntity

from tests.typing import WebSocketGenerator

BYTES_ONE_SECOND = 16000 * 2


def process_events(events: list[assist_pipeline.PipelineEvent]) -> list[dict]:
    """Process events to remove dynamic values."""
    processed = []
    for event in events:
        as_dict = asdict(event)
        as_dict.pop("timestamp")
        if as_dict["type"] == assist_pipeline.PipelineEventType.RUN_START:
            as_dict["data"]["pipeline"] = ANY
        processed.append(as_dict)

    return processed


async def test_pipeline_from_audio_stream_auto(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, no pipeline is specified.
    """

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

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
        stt_stream=audio_data(),
    )

    assert process_events(events) == snapshot
    assert mock_stt_provider.received == [b"part1", b"part2"]


async def test_pipeline_from_audio_stream_legacy(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSttProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, a pipeline using a legacy stt engine is used.
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    # Create a pipeline using an stt entity
    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": "en-US",
            "language": "en",
            "name": "test_name",
            "stt_engine": "test",
            "stt_language": "en-US",
            "tts_engine": "test",
            "tts_language": "en-US",
            "tts_voice": "Arnold Schwarzenegger",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]

    # Use the created pipeline
    await assist_pipeline.async_pipeline_from_audio_stream(
        hass,
        context=Context(),
        event_callback=events.append,
        stt_metadata=stt.SpeechMetadata(
            language="en-UK",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        stt_stream=audio_data(),
        pipeline_id=pipeline_id,
    )

    assert process_events(events) == snapshot
    assert mock_stt_provider.received == [b"part1", b"part2"]


async def test_pipeline_from_audio_stream_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider_entity: MockSttProviderEntity,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, a pipeline using am stt entity is used.
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    # Create a pipeline using an stt entity
    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": "en-US",
            "language": "en",
            "name": "test_name",
            "stt_engine": mock_stt_provider_entity.entity_id,
            "stt_language": "en-US",
            "tts_engine": "test",
            "tts_language": "en-US",
            "tts_voice": "Arnold Schwarzenegger",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]

    # Use the created pipeline
    await assist_pipeline.async_pipeline_from_audio_stream(
        hass,
        context=Context(),
        event_callback=events.append,
        stt_metadata=stt.SpeechMetadata(
            language="en-UK",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        stt_stream=audio_data(),
        pipeline_id=pipeline_id,
    )

    assert process_events(events) == snapshot
    assert mock_stt_provider_entity.received == [b"part1", b"part2"]


async def test_pipeline_from_audio_stream_no_stt(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSttProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, the pipeline does not support stt
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    # Create a pipeline without stt support
    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": "en-US",
            "language": "en",
            "name": "test_name",
            "stt_engine": None,
            "stt_language": None,
            "tts_engine": "test",
            "tts_language": "en-AU",
            "tts_voice": "Arnold Schwarzenegger",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]

    # Try to use the created pipeline
    with pytest.raises(assist_pipeline.pipeline.PipelineRunValidationError):
        await assist_pipeline.async_pipeline_from_audio_stream(
            hass,
            context=Context(),
            event_callback=events.append,
            stt_metadata=stt.SpeechMetadata(
                language="en-UK",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_data(),
            pipeline_id=pipeline_id,
        )

    assert not events


async def test_pipeline_from_audio_stream_unknown_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSttProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, the pipeline does not exist.
    """
    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    # Try to use the created pipeline
    with pytest.raises(assist_pipeline.PipelineNotFound):
        await assist_pipeline.async_pipeline_from_audio_stream(
            hass,
            context=Context(),
            event_callback=events.append,
            stt_metadata=stt.SpeechMetadata(
                language="en-UK",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_data(),
            pipeline_id="blah",
        )

    assert not events


async def test_pipeline_from_audio_stream_wake_word(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream with wake word."""

    events: list[assist_pipeline.PipelineEvent] = []

    # [0, 1, ...]
    wake_chunk_1 = bytes(it.islice(it.cycle(range(256)), BYTES_ONE_SECOND))

    # [0, 2, ...]
    wake_chunk_2 = bytes(it.islice(it.cycle(range(0, 256, 2)), BYTES_ONE_SECOND))

    async def audio_data():
        yield wake_chunk_1  # 1 second
        yield wake_chunk_2  # 1 second
        yield b"wake word!"
        yield b"part1"
        yield b"part2"
        yield b"end"
        yield b""

    def continue_stt(self, chunk):
        # Ensure stt_vad_start event is triggered
        self.in_command = True

        # Stop on fake end chunk to trigger stt_vad_end
        return chunk != b"end"

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.VoiceCommandSegmenter.process",
        continue_stt,
    ):
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
            stt_stream=audio_data(),
            start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
            wake_word_settings=assist_pipeline.WakeWordSettings(
                audio_seconds_to_buffer=1.5
            ),
        )

    assert process_events(events) == snapshot

    # 1. Half of wake_chunk_1 + all wake_chunk_2
    # 2. queued audio (from mock wake word entity)
    # 3. part1
    # 4. part2
    assert len(mock_stt_provider.received) == 4

    first_chunk = mock_stt_provider.received[0]
    assert first_chunk == wake_chunk_1[len(wake_chunk_1) // 2 :] + wake_chunk_2

    assert mock_stt_provider.received[1:] == [b"queued audio", b"part1", b"part2"]


async def test_pipeline_save_audio(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_supporting_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test saving audio during a pipeline run."""
    with tempfile.TemporaryDirectory() as temp_dir_str:
        # Enable audio recording to temporary directory
        temp_dir = Path(temp_dir_str)
        assert await async_setup_component(
            hass,
            "assist_pipeline",
            {"assist_pipeline": {"debug_recording_dir": temp_dir_str}},
        )

        pipeline = assist_pipeline.async_get_pipeline(hass)
        events: list[assist_pipeline.PipelineEvent] = []

        # Pad out to an even number of bytes since these "samples" will be saved
        # as 16-bit values.
        async def audio_data():
            yield b"wake word_"
            # queued audio
            yield b"part1_"
            yield b"part2_"
            yield b""

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
            stt_stream=audio_data(),
            pipeline_id=pipeline.id,
            start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
            end_stage=assist_pipeline.PipelineStage.STT,
        )

        pipeline_dirs = list(temp_dir.iterdir())

        # Only one pipeline run
        # <debug_recording_dir>/<pipeline.name>/<run.id>
        assert len(pipeline_dirs) == 1
        assert pipeline_dirs[0].is_dir()
        assert pipeline_dirs[0].name == pipeline.name

        # Wake and stt files
        run_dirs = list(pipeline_dirs[0].iterdir())
        assert run_dirs[0].is_dir()
        run_files = list(run_dirs[0].iterdir())

        assert len(run_files) == 2
        wake_file = run_files[0] if "wake" in run_files[0].name else run_files[1]
        stt_file = run_files[0] if "stt" in run_files[0].name else run_files[1]
        assert wake_file != stt_file

        # Verify wake file
        with wave.open(str(wake_file), "rb") as wake_wav:
            wake_data = wake_wav.readframes(wake_wav.getnframes())
            assert wake_data == b"wake word_"

        # Verify stt file
        with wave.open(str(stt_file), "rb") as stt_wav:
            stt_data = stt_wav.readframes(stt_wav.getnframes())
            assert stt_data == b"queued audiopart1_part2_"


async def test_pipeline_saved_audio_with_device_id(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_supporting_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that saved audio directory uses device id."""
    device_id = "test-device-id"

    with tempfile.TemporaryDirectory() as temp_dir_str:
        # Enable audio recording to temporary directory
        temp_dir = Path(temp_dir_str)
        assert await async_setup_component(
            hass,
            "assist_pipeline",
            {"assist_pipeline": {"debug_recording_dir": temp_dir_str}},
        )

        def event_callback(event: assist_pipeline.PipelineEvent):
            if event.type == "run-end":
                # Verify that saved audio directory is named after device id
                device_dirs = list(temp_dir.iterdir())
                assert device_dirs[0].name == device_id

        async def audio_data():
            yield b"not used"

        # Force a timeout during wake word detection
        with patch.object(
            mock_wake_word_provider_entity,
            "async_process_audio_stream",
            side_effect=assist_pipeline.error.WakeWordTimeoutError(
                code="timeout", message="timeout"
            ),
        ):
            await assist_pipeline.async_pipeline_from_audio_stream(
                hass,
                context=Context(),
                event_callback=event_callback,
                stt_metadata=stt.SpeechMetadata(
                    language="",
                    format=stt.AudioFormats.WAV,
                    codec=stt.AudioCodecs.PCM,
                    bit_rate=stt.AudioBitRates.BITRATE_16,
                    sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                    channel=stt.AudioChannels.CHANNEL_MONO,
                ),
                stt_stream=audio_data(),
                start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
                end_stage=assist_pipeline.PipelineStage.STT,
                device_id=device_id,
            )


async def test_pipeline_saved_audio_write_error(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_supporting_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that saved audio thread closes WAV file even if there's a write error."""
    with tempfile.TemporaryDirectory() as temp_dir_str:
        # Enable audio recording to temporary directory
        temp_dir = Path(temp_dir_str)
        assert await async_setup_component(
            hass,
            "assist_pipeline",
            {"assist_pipeline": {"debug_recording_dir": temp_dir_str}},
        )

        def event_callback(event: assist_pipeline.PipelineEvent):
            if event.type == "run-end":
                # Verify WAV file exists, but contains no data
                pipeline_dirs = list(temp_dir.iterdir())
                run_dirs = list(pipeline_dirs[0].iterdir())
                wav_path = next(run_dirs[0].iterdir())
                with wave.open(str(wav_path), "rb") as wav_file:
                    assert wav_file.getnframes() == 0

        async def audio_data():
            yield b"not used"

        # Force a timeout during wake word detection
        with patch("wave.Wave_write.writeframes", raises=RuntimeError()):
            await assist_pipeline.async_pipeline_from_audio_stream(
                hass,
                context=Context(),
                event_callback=event_callback,
                stt_metadata=stt.SpeechMetadata(
                    language="",
                    format=stt.AudioFormats.WAV,
                    codec=stt.AudioCodecs.PCM,
                    bit_rate=stt.AudioBitRates.BITRATE_16,
                    sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                    channel=stt.AudioChannels.CHANNEL_MONO,
                ),
                stt_stream=audio_data(),
                start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
                end_stage=assist_pipeline.PipelineStage.STT,
            )
