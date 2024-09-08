"""Test ESPHome voice assistant server."""

import asyncio
from collections.abc import Awaitable, Callable
import io
import socket
from unittest.mock import ANY, Mock, patch
import wave

from aioesphomeapi import (
    APIClient,
    EntityInfo,
    EntityState,
    MediaPlayerFormatPurpose,
    MediaPlayerInfo,
    MediaPlayerSupportedFormat,
    UserService,
    VoiceAssistantAudioSettings,
    VoiceAssistantCommandFlag,
    VoiceAssistantEventType,
    VoiceAssistantFeature,
    VoiceAssistantTimerEventType,
)
import pytest

from homeassistant.components import assist_satellite, tts
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.assist_satellite.entity import (
    AssistSatelliteEntity,
    AssistSatelliteState,
)
from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.assist_satellite import (
    EsphomeAssistSatellite,
    VoiceAssistantUDPServer,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, intent as intent_helper
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity_component import EntityComponent

from .conftest import MockESPHomeDevice


def get_satellite_entity(
    hass: HomeAssistant, mac_address: str
) -> EsphomeAssistSatellite | None:
    """Get the satellite entity for a device."""
    ent_reg = er.async_get(hass)
    satellite_entity_id = ent_reg.async_get_entity_id(
        Platform.ASSIST_SATELLITE, DOMAIN, f"{mac_address}-assist_satellite"
    )
    if satellite_entity_id is None:
        return None

    component: EntityComponent[AssistSatelliteEntity] = hass.data[
        assist_satellite.DOMAIN
    ]
    if (entity := component.get_entity(satellite_entity_id)) is not None:
        assert isinstance(entity, EsphomeAssistSatellite)
        return entity

    return None


@pytest.fixture
def mock_wav() -> bytes:
    """Return test WAV audio."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(b"test-wav")

        return wav_io.getvalue()


async def test_no_satellite_without_voice_assistant(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test that an assist satellite entity is not created if a voice assistant is not present."""
    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={},
    )
    await hass.async_block_till_done()

    # No satellite entity should be created
    assert get_satellite_entity(hass, mock_device.device_info.mac_address) is None


async def test_pipeline_api_audio(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    mock_wav: bytes,
) -> None:
    """Test a complete pipeline run with API audio (over the TCP connection)."""
    conversation_id = "test-conversation-id"
    media_url = "http://test.url"
    media_id = "test-media-id"

    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.SPEAKER
            | VoiceAssistantFeature.API_AUDIO
        },
    )
    await hass.async_block_till_done()
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mock_device.entry.unique_id)}
    )

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    # Block TTS streaming until we're ready.
    # This makes it easier to verify the order of pipeline events.
    stream_tts_audio_ready = asyncio.Event()
    original_stream_tts_audio = satellite._stream_tts_audio

    async def _stream_tts_audio(*args, **kwargs):
        await stream_tts_audio_ready.wait()
        await original_stream_tts_audio(*args, **kwargs)

    async def async_pipeline_from_audio_stream(*args, device_id, **kwargs):
        assert device_id == dev.id

        stt_stream = kwargs["stt_stream"]

        chunks = [chunk async for chunk in stt_stream]

        # Verify test API audio
        assert chunks == [b"test-mic"]

        event_callback = kwargs["event_callback"]

        # Test unknown event type
        event_callback(
            PipelineEvent(
                type="unknown-event",
                data={},
            )
        )

        mock_client.send_voice_assistant_event.assert_not_called()

        # Test error event
        event_callback(
            PipelineEvent(
                type=PipelineEventType.ERROR,
                data={"code": "test-error-code", "message": "test-error-message"},
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_ERROR,
            {"code": "test-error-code", "message": "test-error-message"},
        )

        # Wake word
        assert satellite.state == AssistSatelliteState.LISTENING_WAKE_WORD

        event_callback(
            PipelineEvent(
                type=PipelineEventType.WAKE_WORD_START,
                data={
                    "entity_id": "test-wake-word-entity-id",
                    "metadata": {},
                    "timeout": 0,
                },
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_START,
            {},
        )

        # Test no wake word detected
        event_callback(
            PipelineEvent(
                type=PipelineEventType.WAKE_WORD_END, data={"wake_word_output": {}}
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_ERROR,
            {"code": "no_wake_word", "message": "No wake word detected"},
        )

        # Correct wake word detection
        event_callback(
            PipelineEvent(
                type=PipelineEventType.WAKE_WORD_END,
                data={"wake_word_output": {"wake_word_phrase": "test-wake-word"}},
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END,
            {},
        )

        # STT
        event_callback(
            PipelineEvent(
                type=PipelineEventType.STT_START,
                data={"engine": "test-stt-engine", "metadata": {}},
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_STT_START,
            {},
        )
        assert satellite.state == AssistSatelliteState.LISTENING_COMMAND

        event_callback(
            PipelineEvent(
                type=PipelineEventType.STT_END,
                data={"stt_output": {"text": "test-stt-text"}},
            )
        )
        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_STT_END,
            {"text": "test-stt-text"},
        )

        # Intent
        event_callback(
            PipelineEvent(
                type=PipelineEventType.INTENT_START,
                data={
                    "engine": "test-intent-engine",
                    "language": hass.config.language,
                    "intent_input": "test-intent-text",
                    "conversation_id": conversation_id,
                    "device_id": device_id,
                },
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_START,
            {},
        )
        assert satellite.state == AssistSatelliteState.PROCESSING

        event_callback(
            PipelineEvent(
                type=PipelineEventType.INTENT_END,
                data={"intent_output": {"conversation_id": conversation_id}},
            )
        )
        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END,
            {"conversation_id": conversation_id},
        )

        # TTS
        event_callback(
            PipelineEvent(
                type=PipelineEventType.TTS_START,
                data={
                    "engine": "test-stt-engine",
                    "language": hass.config.language,
                    "voice": "test-voice",
                    "tts_input": "test-tts-text",
                },
            )
        )

        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START,
            {"text": "test-tts-text"},
        )
        assert satellite.state == AssistSatelliteState.RESPONDING

        # Should return mock_wav audio
        event_callback(
            PipelineEvent(
                type=PipelineEventType.TTS_END,
                data={"tts_output": {"url": media_url, "media_id": media_id}},
            )
        )
        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END,
            {"url": media_url},
        )

        event_callback(PipelineEvent(type=PipelineEventType.RUN_END))
        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END,
            {},
        )

        # Allow TTS streaming to proceed
        stream_tts_audio_ready.set()

    pipeline_finished = asyncio.Event()
    original_handle_pipeline_finished = satellite.handle_pipeline_finished

    def handle_pipeline_finished():
        original_handle_pipeline_finished()
        pipeline_finished.set()

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        return ("wav", mock_wav)

    tts_finished = asyncio.Event()
    original_tts_response_finished = satellite.tts_response_finished

    def tts_response_finished():
        original_tts_response_finished()
        tts_finished.set()

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
        patch.object(satellite, "handle_pipeline_finished", handle_pipeline_finished),
        patch.object(satellite, "_stream_tts_audio", _stream_tts_audio),
        patch.object(satellite, "tts_response_finished", tts_response_finished),
    ):
        # Should be cleared at pipeline start
        satellite._audio_queue.put_nowait(b"leftover-data")

        # Should be cancelled at pipeline start
        mock_tts_streaming_task = Mock()
        satellite._tts_streaming_task = mock_tts_streaming_task

        async with asyncio.timeout(1):
            await satellite.handle_pipeline_start(
                conversation_id=conversation_id,
                flags=VoiceAssistantCommandFlag.USE_WAKE_WORD,
                audio_settings=VoiceAssistantAudioSettings(),
                wake_word_phrase="",
            )
            mock_tts_streaming_task.cancel.assert_called_once()
            await satellite.handle_audio(b"test-mic")
            await satellite.handle_pipeline_stop()
            await pipeline_finished.wait()

            await tts_finished.wait()

    # Verify TTS streaming events.
    # These are definitely the last two events because we blocked TTS streaming
    # until after RUN_END above.
    assert mock_client.send_voice_assistant_event.call_args_list[-2].args == (
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START,
        {},
    )
    assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END,
        {},
    )

    # Verify TTS WAV audio chunk came through
    mock_client.send_voice_assistant_audio.assert_called_once_with(b"test-wav")


@pytest.mark.usefixtures("socket_enabled")
async def test_pipeline_udp_audio(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    mock_wav: bytes,
) -> None:
    """Test a complete pipeline run with legacy UDP audio.

    This test is not as comprehensive as test_pipeline_api_audio since we're
    mainly focused on the UDP server.
    """
    conversation_id = "test-conversation-id"
    media_url = "http://test.url"
    media_id = "test-media-id"

    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.SPEAKER
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    mic_audio_event = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, device_id, **kwargs):
        stt_stream = kwargs["stt_stream"]

        chunks = []
        async for chunk in stt_stream:
            chunks.append(chunk)
            mic_audio_event.set()

        # Verify test UDP audio
        assert chunks == [b"test-mic"]

        event_callback = kwargs["event_callback"]

        # STT
        event_callback(
            PipelineEvent(
                type=PipelineEventType.STT_START,
                data={"engine": "test-stt-engine", "metadata": {}},
            )
        )

        event_callback(
            PipelineEvent(
                type=PipelineEventType.STT_END,
                data={"stt_output": {"text": "test-stt-text"}},
            )
        )

        # Intent
        event_callback(
            PipelineEvent(
                type=PipelineEventType.INTENT_START,
                data={
                    "engine": "test-intent-engine",
                    "language": hass.config.language,
                    "intent_input": "test-intent-text",
                    "conversation_id": conversation_id,
                    "device_id": device_id,
                },
            )
        )

        event_callback(
            PipelineEvent(
                type=PipelineEventType.INTENT_END,
                data={"intent_output": {"conversation_id": conversation_id}},
            )
        )

        # TTS
        event_callback(
            PipelineEvent(
                type=PipelineEventType.TTS_START,
                data={
                    "engine": "test-stt-engine",
                    "language": hass.config.language,
                    "voice": "test-voice",
                    "tts_input": "test-tts-text",
                },
            )
        )

        # Should return mock_wav audio
        event_callback(
            PipelineEvent(
                type=PipelineEventType.TTS_END,
                data={"tts_output": {"url": media_url, "media_id": media_id}},
            )
        )

        event_callback(PipelineEvent(type=PipelineEventType.RUN_END))

    pipeline_finished = asyncio.Event()
    original_handle_pipeline_finished = satellite.handle_pipeline_finished

    def handle_pipeline_finished():
        original_handle_pipeline_finished()
        pipeline_finished.set()

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        return ("wav", mock_wav)

    tts_finished = asyncio.Event()
    original_tts_response_finished = satellite.tts_response_finished

    def tts_response_finished():
        original_tts_response_finished()
        tts_finished.set()

    class TestProtocol(asyncio.DatagramProtocol):
        def __init__(self) -> None:
            self.transport = None
            self.data_received: list[bytes] = []

        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data: bytes, addr):
            self.data_received.append(data)

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
        patch.object(satellite, "handle_pipeline_finished", handle_pipeline_finished),
        patch.object(satellite, "tts_response_finished", tts_response_finished),
    ):
        async with asyncio.timeout(1):
            port = await satellite.handle_pipeline_start(
                conversation_id=conversation_id,
                flags=VoiceAssistantCommandFlag(0),  # stt
                audio_settings=VoiceAssistantAudioSettings(),
                wake_word_phrase="",
            )
            assert (port is not None) and (port > 0)

            (
                transport,
                protocol,
            ) = await asyncio.get_running_loop().create_datagram_endpoint(
                TestProtocol, remote_addr=("127.0.0.1", port)
            )
            assert isinstance(protocol, TestProtocol)

            # Send audio over UDP
            transport.sendto(b"test-mic")

            # Wait for audio chunk to be delivered
            await mic_audio_event.wait()

            await satellite.handle_pipeline_stop()
            await pipeline_finished.wait()

            await tts_finished.wait()

    # Verify TTS audio (from UDP)
    assert protocol.data_received == [b"test-wav"]

    # Check that UDP server was stopped
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.bind(("", port))  # will fail if UDP server is still running
    sock.close()


async def test_udp_errors() -> None:
    """Test UDP protocol error conditions."""
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    protocol = VoiceAssistantUDPServer(audio_queue)

    protocol.datagram_received(b"test", ("", 0))
    assert audio_queue.qsize() == 1
    assert (await audio_queue.get()) == b"test"

    # None will stop the pipeline
    protocol.error_received(RuntimeError())
    assert audio_queue.qsize() == 1
    assert (await audio_queue.get()) is None

    # No transport
    assert protocol.transport is None
    protocol.send_audio_bytes(b"test")

    # No remote address
    protocol.transport = Mock()
    protocol.remote_addr = None
    protocol.send_audio_bytes(b"test")
    protocol.transport.sendto.assert_not_called()


async def test_timer_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test that injecting timer events results in the correct api client calls."""

    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.TIMERS
        },
    )
    await hass.async_block_till_done()
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mock_device.entry.unique_id)}
    )

    total_seconds = (1 * 60 * 60) + (2 * 60) + 3
    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_START_TIMER,
        {
            "name": {"value": "test timer"},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=dev.id,
    )

    mock_client.send_voice_assistant_timer_event.assert_called_with(
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED,
        ANY,
        "test timer",
        total_seconds,
        total_seconds,
        True,
    )

    # Increase timer beyond original time and check total_seconds has increased
    mock_client.send_voice_assistant_timer_event.reset_mock()

    total_seconds += 5 * 60
    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_INCREASE_TIMER,
        {
            "name": {"value": "test timer"},
            "minutes": {"value": 5},
        },
        device_id=dev.id,
    )

    mock_client.send_voice_assistant_timer_event.assert_called_with(
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED,
        ANY,
        "test timer",
        total_seconds,
        ANY,
        True,
    )


async def test_unknown_timer_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test that unknown (new) timer event types do not result in api calls."""

    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.TIMERS
        },
    )
    await hass.async_block_till_done()
    assert mock_device.entry.unique_id is not None
    dev = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mock_device.entry.unique_id)}
    )
    assert dev is not None

    with patch(
        "homeassistant.components.esphome.assist_satellite._TIMER_EVENT_TYPES.from_hass",
        side_effect=KeyError,
    ):
        await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_START_TIMER,
            {
                "name": {"value": "test timer"},
                "hours": {"value": 1},
                "minutes": {"value": 2},
                "seconds": {"value": 3},
            },
            device_id=dev.id,
        )

        mock_client.send_voice_assistant_timer_event.assert_not_called()


async def test_streaming_tts_errors(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    mock_wav: bytes,
) -> None:
    """Test error conditions for _stream_tts_audio function."""
    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    # Should not stream if not running
    satellite._is_running = False
    await satellite._stream_tts_audio("test-media-id")
    mock_client.send_voice_assistant_audio.assert_not_called()
    satellite._is_running = True

    # Should only stream WAV
    async def get_mp3(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        return ("mp3", b"")

    with patch(
        "homeassistant.components.tts.async_get_media_source_audio", new=get_mp3
    ):
        await satellite._stream_tts_audio("test-media-id")
        mock_client.send_voice_assistant_audio.assert_not_called()

    # Needs to be the correct sample rate, etc.
    async def get_bad_wav(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(48000)
                wav_file.setsampwidth(2)
                wav_file.setnchannels(1)
                wav_file.writeframes(b"test-wav")

            return ("wav", wav_io.getvalue())

    with patch(
        "homeassistant.components.tts.async_get_media_source_audio", new=get_bad_wav
    ):
        await satellite._stream_tts_audio("test-media-id")
        mock_client.send_voice_assistant_audio.assert_not_called()

    # Check that TTS_STREAM_* events still get sent after cancel
    media_fetched = asyncio.Event()

    async def get_slow_wav(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        media_fetched.set()
        await asyncio.sleep(1)
        return ("wav", mock_wav)

    mock_client.send_voice_assistant_event.reset_mock()
    with patch(
        "homeassistant.components.tts.async_get_media_source_audio", new=get_slow_wav
    ):
        task = asyncio.create_task(satellite._stream_tts_audio("test-media-id"))
        async with asyncio.timeout(1):
            # Wait for media to be fetched
            await media_fetched.wait()

        # Cancel task
        task.cancel()
        await task

        # No audio should have gone out
        mock_client.send_voice_assistant_audio.assert_not_called()
        assert len(mock_client.send_voice_assistant_event.call_args_list) == 2

        # The TTS_STREAM_* events should have gone out
        assert mock_client.send_voice_assistant_event.call_args_list[-2].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START,
            {},
        )
        assert mock_client.send_voice_assistant_event.call_args_list[-1].args == (
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END,
            {},
        )


async def test_tts_format_from_media_player(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test that the text-to-speech format is pulled from the first media player."""
    mock_device: MockESPHomeDevice = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[
            MediaPlayerInfo(
                object_id="mymedia_player",
                key=1,
                name="my media_player",
                unique_id="my_media_player",
                supports_pause=True,
                supported_formats=[
                    MediaPlayerSupportedFormat(
                        format="flac",
                        sample_rate=48000,
                        num_channels=2,
                        purpose=MediaPlayerFormatPurpose.DEFAULT,
                    ),
                    # This is the format that should be used for tts
                    MediaPlayerSupportedFormat(
                        format="mp3",
                        sample_rate=22050,
                        num_channels=1,
                        purpose=MediaPlayerFormatPurpose.ANNOUNCEMENT,
                    ),
                ],
            )
        ],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
    ) as mock_pipeline_from_audio_stream:
        await satellite.handle_pipeline_start(
            conversation_id="",
            flags=0,
            audio_settings=VoiceAssistantAudioSettings(),
            wake_word_phrase=None,
        )

        mock_pipeline_from_audio_stream.assert_called_once()
        kwargs = mock_pipeline_from_audio_stream.call_args_list[0].kwargs

        # Should be ANNOUNCEMENT format from media player
        assert kwargs.get("tts_audio_output") == {
            tts.ATTR_PREFERRED_FORMAT: "mp3",
            tts.ATTR_PREFERRED_SAMPLE_RATE: 22050,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1,
            tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
        }
