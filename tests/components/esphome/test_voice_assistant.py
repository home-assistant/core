"""Test ESPHome voice assistant server."""

from unittest.mock import Mock, patch

from homeassistant.components import esphome, voice_assistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

_TEST_INPUT_TEXT = "This is an input test"
_TEST_OUTPUT_TEXT = "This is an output test"
_TEST_OUTPUT_URL = "output.mp3"


async def test_pipeline_events(hass: HomeAssistant, init_integration) -> None:
    """Test that the pipeline function is called."""
    assert init_integration.state == ConfigEntryState.LOADED

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        event_callback = kwargs["event_callback"]

        # Fake events
        event_callback(
            voice_assistant.PipelineEvent(
                type=voice_assistant.PipelineEventType.STT_START,
                data={},
            )
        )

        event_callback(
            voice_assistant.PipelineEvent(
                type=voice_assistant.PipelineEventType.STT_END,
                data={"stt_output": {"text": _TEST_INPUT_TEXT}},
            )
        )

        event_callback(
            voice_assistant.PipelineEvent(
                type=voice_assistant.PipelineEventType.TTS_START,
                data={"tts_input": _TEST_OUTPUT_TEXT},
            )
        )

        event_callback(
            voice_assistant.PipelineEvent(
                type=voice_assistant.PipelineEventType.TTS_END,
                data={"tts_output": {"url": _TEST_OUTPUT_URL}},
            )
        )

    def handle_event(
        event_type: esphome.VoiceAssistantEventType, data: dict[str, str] | None
    ) -> None:
        if event_type == esphome.VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
            assert data is not None
            assert data["text"] == _TEST_INPUT_TEXT
        elif event_type == esphome.VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START:
            assert data is not None
            assert data["text"] == _TEST_OUTPUT_TEXT
        elif event_type == esphome.VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END:
            assert data is not None
            assert data["url"] == _TEST_OUTPUT_URL

    with patch(
        "homeassistant.components.esphome.voice_assistant.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        server = esphome.voice_assistant.VoiceAssistantUDPServer(hass)
        server.transport = Mock()

        await server.run_pipeline(handle_event)
