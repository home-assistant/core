"""Test the Assist Satellite entity."""

from unittest.mock import patch

import pytest

from homeassistant.components import stt
from homeassistant.components.assist_pipeline import (
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    async_get_pipeline,
    async_update_pipeline,
    vad,
)
from homeassistant.components.assist_satellite import AssistSatelliteState
from homeassistant.components.media_source import PlayMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant

from . import ENTITY_ID
from .conftest import MockAssistSatellite


async def test_entity_state(
    hass: HomeAssistant, init_components: ConfigEntry, entity: MockAssistSatellite
) -> None:
    """Test entity state represent events."""

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    audio_stream = object()

    entity.async_set_context(context)

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream"
    ) as mock_start_pipeline:
        await entity.async_accept_pipeline_from_satellite(audio_stream)

    assert mock_start_pipeline.called
    kwargs = mock_start_pipeline.call_args[1]
    assert kwargs["context"] is context
    assert kwargs["event_callback"] == entity._internal_on_pipeline_event
    assert kwargs["stt_metadata"] == stt.SpeechMetadata(
        language="",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    assert kwargs["stt_stream"] is audio_stream
    assert kwargs["pipeline_id"] is None
    assert kwargs["device_id"] is None
    assert kwargs["tts_audio_output"] == "wav"
    assert kwargs["wake_word_phrase"] is None
    assert kwargs["audio_settings"] == AudioSettings(
        silence_seconds=vad.VadSensitivity.to_seconds(vad.VadSensitivity.DEFAULT)
    )
    assert kwargs["start_stage"] == PipelineStage.STT
    assert kwargs["end_stage"] == PipelineStage.TTS

    for event_type, expected_state in (
        (PipelineEventType.RUN_START, STATE_UNKNOWN),
        (PipelineEventType.RUN_END, AssistSatelliteState.LISTENING_WAKE_WORD),
        (PipelineEventType.WAKE_WORD_START, AssistSatelliteState.LISTENING_WAKE_WORD),
        (PipelineEventType.WAKE_WORD_END, AssistSatelliteState.LISTENING_WAKE_WORD),
        (PipelineEventType.STT_START, AssistSatelliteState.LISTENING_COMMAND),
        (PipelineEventType.STT_VAD_START, AssistSatelliteState.LISTENING_COMMAND),
        (PipelineEventType.STT_VAD_END, AssistSatelliteState.LISTENING_COMMAND),
        (PipelineEventType.STT_END, AssistSatelliteState.LISTENING_COMMAND),
        (PipelineEventType.INTENT_START, AssistSatelliteState.PROCESSING),
        (PipelineEventType.INTENT_END, AssistSatelliteState.PROCESSING),
        (PipelineEventType.TTS_START, AssistSatelliteState.RESPONDING),
        (PipelineEventType.TTS_END, AssistSatelliteState.RESPONDING),
        (PipelineEventType.ERROR, AssistSatelliteState.RESPONDING),
    ):
        kwargs["event_callback"](PipelineEvent(event_type, {}))
        state = hass.states.get(ENTITY_ID)
        assert state.state == expected_state, event_type

    entity.tts_response_finished()
    state = hass.states.get(ENTITY_ID)
    assert state.state == AssistSatelliteState.LISTENING_WAKE_WORD


@pytest.mark.parametrize(
    ("service_data", "expected_params"),
    [
        (
            {"message": "Hello"},
            ("Hello", "https://www.home-assistant.io/resolved.mp3"),
        ),
        (
            {
                "message": "Hello",
                "media_id": "http://example.com/bla.mp3",
            },
            ("Hello", "http://example.com/bla.mp3"),
        ),
        (
            {"media_id": "http://example.com/bla.mp3"},
            ("", "http://example.com/bla.mp3"),
        ),
    ],
)
async def test_announce(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    service_data: dict,
    expected_params: tuple[str, str],
) -> None:
    """Test announcing on a device."""
    await async_update_pipeline(
        hass,
        async_get_pipeline(hass),
        tts_engine="tts.mock_entity",
        tts_language="en",
    )

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.tts_generate_media_source_id",
            return_value="media-source://bla",
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=PlayMedia(
                url="https://www.home-assistant.io/resolved.mp3",
                mime_type="audio/mp3",
            ),
        ),
    ):
        await hass.services.async_call(
            "assist_satellite",
            "announce",
            service_data,
            target={"entity_id": "assist_satellite.test_entity"},
            blocking=True,
        )

    assert entity.announcements[0] == expected_params
