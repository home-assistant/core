"""Test Voice Assistant init."""

import asyncio
from dataclasses import asdict
import itertools as it
from pathlib import Path
import tempfile
from unittest.mock import ANY, patch
import wave

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import assist_pipeline, media_source, stt, tts
from homeassistant.components.assist_pipeline.const import (
    BYTES_PER_CHUNK,
    CONF_DEBUG_RECORDING_DIR,
    DOMAIN,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    BYTES_ONE_SECOND,
    MockSTTProvider,
    MockSTTProviderEntity,
    MockTTSProvider,
    MockWakeWordEntity,
    make_10ms_chunk,
)

from tests.typing import ClientSessionGenerator, WebSocketGenerator


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
    mock_stt_provider_entity: MockSTTProviderEntity,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, no pipeline is specified.
    """

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
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
        audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
    )

    assert process_events(events) == snapshot
    assert len(mock_stt_provider_entity.received) == 2
    assert mock_stt_provider_entity.received[0].startswith(b"part1")
    assert mock_stt_provider_entity.received[1].startswith(b"part2")


async def test_pipeline_from_audio_stream_legacy(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSTTProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, a pipeline using a legacy stt engine is used.
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
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
            "wake_word_entity": None,
            "wake_word_id": None,
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
        audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
    )

    assert process_events(events) == snapshot
    assert len(mock_stt_provider.received) == 2
    assert mock_stt_provider.received[0].startswith(b"part1")
    assert mock_stt_provider.received[1].startswith(b"part2")


async def test_pipeline_from_audio_stream_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider_entity: MockSTTProviderEntity,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, a pipeline using am stt entity is used.
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
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
            "wake_word_entity": None,
            "wake_word_id": None,
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
        audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
    )

    assert process_events(events) == snapshot
    assert len(mock_stt_provider_entity.received) == 2
    assert mock_stt_provider_entity.received[0].startswith(b"part1")
    assert mock_stt_provider_entity.received[1].startswith(b"part2")


async def test_pipeline_from_audio_stream_no_stt(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSTTProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, the pipeline does not support stt
    """
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
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
            "wake_word_entity": None,
            "wake_word_id": None,
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
            audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
        )

    assert not events


async def test_pipeline_from_audio_stream_unknown_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_stt_provider: MockSTTProvider,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream.

    In this test, the pipeline does not exist.
    """
    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
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
    mock_stt_provider_entity: MockSTTProviderEntity,
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

    samples_per_chunk = 160  # 10ms @ 16Khz
    bytes_per_chunk = samples_per_chunk * 2  # 16-bit

    async def audio_data():
        # 1 second in chunks
        i = 0
        while i < len(wake_chunk_1):
            yield wake_chunk_1[i : i + bytes_per_chunk]
            i += bytes_per_chunk

        # 1 second in chunks
        i = 0
        while i < len(wake_chunk_2):
            yield wake_chunk_2[i : i + bytes_per_chunk]
            i += bytes_per_chunk

        for header in (b"wake word!", b"part1", b"part2"):
            yield make_10ms_chunk(header)

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
        start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
        wake_word_settings=assist_pipeline.WakeWordSettings(
            audio_seconds_to_buffer=1.5
        ),
        audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
    )

    assert process_events(events) == snapshot

    # 1. Half of wake_chunk_1 + all wake_chunk_2
    # 2. queued audio (from mock wake word entity)
    # 3. part1
    # 4. part2
    assert len(mock_stt_provider_entity.received) > 3

    first_chunk = bytes(
        [c_byte for c in mock_stt_provider_entity.received[:-3] for c_byte in c]
    )
    assert first_chunk == wake_chunk_1[len(wake_chunk_1) // 2 :] + wake_chunk_2

    assert mock_stt_provider_entity.received[-3] == b"queued audio"
    assert mock_stt_provider_entity.received[-2].startswith(b"part1")
    assert mock_stt_provider_entity.received[-1].startswith(b"part2")


async def test_pipeline_save_audio(
    hass: HomeAssistant,
    mock_stt_provider: MockSTTProvider,
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
            DOMAIN,
            {DOMAIN: {CONF_DEBUG_RECORDING_DIR: temp_dir_str}},
        )

        pipeline = assist_pipeline.async_get_pipeline(hass)
        events: list[assist_pipeline.PipelineEvent] = []

        async def audio_data():
            yield make_10ms_chunk(b"wake word")
            # queued audio
            yield make_10ms_chunk(b"part1")
            yield make_10ms_chunk(b"part2")
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
            audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
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
            assert wake_data.startswith(b"wake word")

        # Verify stt file
        with wave.open(str(stt_file), "rb") as stt_wav:
            stt_data = stt_wav.readframes(stt_wav.getnframes())
            assert stt_data.startswith(b"queued audio")
            stt_data = stt_data[len(b"queued audio") :]
            assert stt_data.startswith(b"part1")
            stt_data = stt_data[BYTES_PER_CHUNK:]
            assert stt_data.startswith(b"part2")


async def test_pipeline_saved_audio_with_device_id(
    hass: HomeAssistant,
    mock_stt_provider: MockSTTProvider,
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
            DOMAIN,
            {DOMAIN: {CONF_DEBUG_RECORDING_DIR: temp_dir_str}},
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
    mock_stt_provider: MockSTTProvider,
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
            DOMAIN,
            {DOMAIN: {CONF_DEBUG_RECORDING_DIR: temp_dir_str}},
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


async def test_pipeline_saved_audio_empty_queue(
    hass: HomeAssistant,
    mock_stt_provider: MockSTTProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_supporting_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that saved audio thread closes WAV file even if there's an empty queue."""
    with tempfile.TemporaryDirectory() as temp_dir_str:
        # Enable audio recording to temporary directory
        temp_dir = Path(temp_dir_str)
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_DEBUG_RECORDING_DIR: temp_dir_str}},
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
            # Force timeout in _pipeline_debug_recording_thread_proc
            await asyncio.sleep(1)
            yield b"not used"

        # Wrap original function to time out immediately
        _pipeline_debug_recording_thread_proc = (
            assist_pipeline.pipeline._pipeline_debug_recording_thread_proc
        )

        def proc_wrapper(run_recording_dir, queue):
            _pipeline_debug_recording_thread_proc(
                run_recording_dir, queue, message_timeout=0
            )

        with patch(
            "homeassistant.components.assist_pipeline.pipeline._pipeline_debug_recording_thread_proc",
            proc_wrapper,
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
            )


async def test_wake_word_detection_aborted(
    hass: HomeAssistant,
    mock_stt_provider: MockSTTProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a pipeline from an audio stream with wake word."""

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"silence!")
        yield make_10ms_chunk(b"wake word!")
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
        yield b""

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        conversation_id=None,
        device_id=None,
        stt_metadata=stt.SpeechMetadata(
            language="",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        stt_stream=audio_data(),
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output=None,
            wake_word_settings=assist_pipeline.WakeWordSettings(
                audio_seconds_to_buffer=1.5
            ),
            audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
        ),
    )
    await pipeline_input.validate()

    updates = pipeline.to_json()
    updates.pop("id")
    await pipeline_store.async_update_item(
        pipeline_id,
        updates,
    )
    await pipeline_input.execute()

    assert process_events(events) == snapshot


def test_pipeline_run_equality(hass: HomeAssistant, init_components) -> None:
    """Test that pipeline run equality uses unique id."""

    def event_callback(event):
        pass

    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass)
    run_1 = assist_pipeline.pipeline.PipelineRun(
        hass,
        context=Context(),
        pipeline=pipeline,
        start_stage=assist_pipeline.PipelineStage.STT,
        end_stage=assist_pipeline.PipelineStage.TTS,
        event_callback=event_callback,
    )
    run_2 = assist_pipeline.pipeline.PipelineRun(
        hass,
        context=Context(),
        pipeline=pipeline,
        start_stage=assist_pipeline.PipelineStage.STT,
        end_stage=assist_pipeline.PipelineStage.TTS,
        event_callback=event_callback,
    )

    assert run_1 == run_1  # noqa: PLR0124
    assert run_1 != run_2
    assert run_1 != 1234


async def test_tts_audio_output(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test using tts_audio_output with wav sets options correctly."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        conversation_id=None,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output="wav",
        ),
    )
    await pipeline_input.validate()

    # Verify TTS audio settings
    assert pipeline_input.run.tts_options is not None
    assert pipeline_input.run.tts_options.get(tts.ATTR_PREFERRED_FORMAT) == "wav"
    assert pipeline_input.run.tts_options.get(tts.ATTR_PREFERRED_SAMPLE_RATE) == 16000
    assert pipeline_input.run.tts_options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS) == 1

    with patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio:
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                media_id = event.data["tts_output"]["media_id"]
                resolved = await media_source.async_resolve_media(hass, media_id, None)
                await client.get(resolved.url)

        # Ensure that no unsupported options were passed in
        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]
        extra_options = set(options).difference(mock_tts_provider.supported_options)
        assert len(extra_options) == 0, extra_options


async def test_tts_wav_preferred_format(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that preferred format options are given to the TTS system if supported."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        conversation_id=None,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output="wav",
        ),
    )
    await pipeline_input.validate()

    # Make the TTS provider support preferred format options
    supported_options = list(mock_tts_provider.supported_options or [])
    supported_options.extend(
        [
            tts.ATTR_PREFERRED_FORMAT,
            tts.ATTR_PREFERRED_SAMPLE_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS,
            tts.ATTR_PREFERRED_SAMPLE_BYTES,
        ]
    )

    with (
        patch.object(mock_tts_provider, "_supported_options", supported_options),
        patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio,
    ):
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                media_id = event.data["tts_output"]["media_id"]
                resolved = await media_source.async_resolve_media(hass, media_id, None)
                await client.get(resolved.url)

        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]

        # We should have received preferred format options in get_tts_audio
        assert options.get(tts.ATTR_PREFERRED_FORMAT) == "wav"
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_RATE)) == 16000
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS)) == 1
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_BYTES)) == 2


async def test_tts_dict_preferred_format(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that preferred format options are given to the TTS system if supported."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        conversation_id=None,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output={
                tts.ATTR_PREFERRED_FORMAT: "flac",
                tts.ATTR_PREFERRED_SAMPLE_RATE: 48000,
                tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 2,
                tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
            },
        ),
    )
    await pipeline_input.validate()

    # Make the TTS provider support preferred format options
    supported_options = list(mock_tts_provider.supported_options or [])
    supported_options.extend(
        [
            tts.ATTR_PREFERRED_FORMAT,
            tts.ATTR_PREFERRED_SAMPLE_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS,
            tts.ATTR_PREFERRED_SAMPLE_BYTES,
        ]
    )

    with (
        patch.object(mock_tts_provider, "_supported_options", supported_options),
        patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio,
    ):
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                media_id = event.data["tts_output"]["media_id"]
                resolved = await media_source.async_resolve_media(hass, media_id, None)
                await client.get(resolved.url)

        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]

        # We should have received preferred format options in get_tts_audio
        assert options.get(tts.ATTR_PREFERRED_FORMAT) == "flac"
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_RATE)) == 48000
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS)) == 2
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_BYTES)) == 2
