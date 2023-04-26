"""Test ESPHome voice assistant server."""

import asyncio
import socket
from unittest.mock import Mock, patch

import async_timeout
import pytest

from homeassistant.components import assist_pipeline, esphome
from homeassistant.components.esphome import DomainData
from homeassistant.components.esphome.voice_assistant import VoiceAssistantUDPServer
from homeassistant.core import HomeAssistant

_TEST_INPUT_TEXT = "This is an input test"
_TEST_OUTPUT_TEXT = "This is an output test"
_TEST_OUTPUT_URL = "output.mp3"


@pytest.fixture
def voice_assistant_udp_server_v1(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> VoiceAssistantUDPServer:
    """Return the UDP server."""
    entry_data = DomainData.get(hass).get_entry_data(mock_voice_assistant_v1_entry)
    return VoiceAssistantUDPServer(hass, entry_data)


async def test_pipeline_events(
    hass: HomeAssistant, voice_assistant_udp_server_v1: VoiceAssistantUDPServer
) -> None:
    """Test that the pipeline function is called."""

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        event_callback = kwargs["event_callback"]

        # Fake events
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_START,
                data={},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": _TEST_INPUT_TEXT}},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_START,
                data={"tts_input": _TEST_OUTPUT_TEXT},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
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
        voice_assistant_udp_server_v1.transport = Mock()

        await voice_assistant_udp_server_v1.run_pipeline(handle_event)


async def test_udp_server(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
    voice_assistant_udp_server_v1: VoiceAssistantUDPServer,
) -> None:
    """Test the UDP server runs and queues incoming data."""
    port_to_use = unused_udp_port_factory()

    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT", new=port_to_use
    ):
        port = await voice_assistant_udp_server_v1.start_server()
        assert port == port_to_use

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        assert voice_assistant_udp_server_v1.queue.qsize() == 0
        sock.sendto(b"test", ("127.0.0.1", port))

        # Give the socket some time to send/receive the data
        async with async_timeout.timeout(1):
            while voice_assistant_udp_server_v1.queue.qsize() == 0:
                await asyncio.sleep(0.1)

        assert voice_assistant_udp_server_v1.queue.qsize() == 1

        voice_assistant_udp_server_v1.stop()

        assert voice_assistant_udp_server_v1.transport.is_closing()


async def test_udp_server_multiple(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
    voice_assistant_udp_server_v1: VoiceAssistantUDPServer,
) -> None:
    """Test that the UDP server raises an error if started twice."""
    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ):
        await voice_assistant_udp_server_v1.start_server()

    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ), pytest.raises(RuntimeError):
        pass
        await voice_assistant_udp_server_v1.start_server()


async def test_udp_server_after_stopped(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
    voice_assistant_udp_server_v1: VoiceAssistantUDPServer,
) -> None:
    """Test that the UDP server raises an error if started after stopped."""
    voice_assistant_udp_server_v1.stop()
    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ), pytest.raises(RuntimeError):
        await voice_assistant_udp_server_v1.start_server()
