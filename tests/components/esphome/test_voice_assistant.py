"""Test ESPHome voice assistant server."""

import asyncio
import socket
from unittest.mock import Mock, patch

import async_timeout
import pytest

from homeassistant.components import assist_pipeline, esphome
from homeassistant.core import HomeAssistant

_TEST_INPUT_TEXT = "This is an input test"
_TEST_OUTPUT_TEXT = "This is an output test"
_TEST_OUTPUT_URL = "output.mp3"


async def test_pipeline_events(hass: HomeAssistant) -> None:
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
        server = esphome.voice_assistant.VoiceAssistantUDPServer(hass)
        server.transport = Mock()

        await server.run_pipeline(handle_event)


async def test_udp_server(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
) -> None:
    """Test the UDP server runs and queues incoming data."""
    port_to_use = unused_udp_port_factory()

    server = esphome.voice_assistant.VoiceAssistantUDPServer(hass)
    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT", new=port_to_use
    ):
        port = await server.start_server()
        assert port == port_to_use

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        assert server.queue.qsize() == 0
        sock.sendto(b"test", ("127.0.0.1", port))

        # Give the socket some time to send/receive the data
        async with async_timeout.timeout(1):
            while server.queue.qsize() == 0:
                await asyncio.sleep(0.1)

        assert server.queue.qsize() == 1

        server.stop()

        assert server.transport.is_closing()


async def test_udp_server_multiple(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
) -> None:
    """Test that the UDP server raises an error if started twice."""
    server = esphome.voice_assistant.VoiceAssistantUDPServer(hass)
    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ):
        await server.start_server()

    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ), pytest.raises(RuntimeError):
        pass
        await server.start_server()


async def test_udp_server_after_stopped(
    hass: HomeAssistant,
    socket_enabled,
    unused_udp_port_factory,
) -> None:
    """Test that the UDP server raises an error if started after stopped."""
    server = esphome.voice_assistant.VoiceAssistantUDPServer(hass)
    server.stop()
    with patch(
        "homeassistant.components.esphome.voice_assistant.UDP_PORT",
        new=unused_udp_port_factory(),
    ), pytest.raises(RuntimeError):
        await server.start_server()
