"""Test Voice Assistant init."""
from dataclasses import asdict
from unittest.mock import ANY

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import assist_pipeline, stt
from homeassistant.core import Context, HomeAssistant

from .conftest import MockSttProvider, MockSttProviderEntity

from tests.typing import WebSocketGenerator


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

    events = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    await assist_pipeline.async_pipeline_from_audio_stream(
        hass,
        Context(),
        events.append,
        stt.SpeechMetadata(
            language="",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        audio_data(),
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

    events = []

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
        Context(),
        events.append,
        stt.SpeechMetadata(
            language="en-UK",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        audio_data(),
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

    events = []

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
        Context(),
        events.append,
        stt.SpeechMetadata(
            language="en-UK",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        audio_data(),
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

    events = []

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
            Context(),
            events.append,
            stt.SpeechMetadata(
                language="en-UK",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            audio_data(),
            pipeline_id=pipeline_id,
        )

    assert not events
