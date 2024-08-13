"""Test VoIP protocol."""

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import wave

import pytest
from syrupy.assertion import SnapshotAssertion
from voip_utils import CallInfo

from homeassistant.components import assist_pipeline, assist_satellite, voip
from homeassistant.components.assist_satellite import AssistSatelliteState
from homeassistant.components.voip import HassVoipDatagramProtocol
from homeassistant.components.voip.assist_satellite import VoipAssistSatellite
from homeassistant.components.voip.devices import VoIPDevice, VoIPDevices
from homeassistant.components.voip.voip import PreRecordMessageProtocol, make_protocol
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit
_MEDIA_ID = "12345"


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


def _empty_wav() -> bytes:
    """Return bytes of an empty WAV file."""
    with io.BytesIO() as wav_io:
        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        with wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)

        return wav_io.getvalue()


async def test_is_valid_call(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    call_info: CallInfo,
) -> None:
    """Test that a call is now allowed from an unknown device."""
    assert await async_setup_component(hass, "voip", {})
    protocol = HassVoipDatagramProtocol(hass, voip_devices)
    assert not protocol.is_valid_call(call_info)

    ent_reg = er.async_get(hass)
    allowed_call_entity_id = ent_reg.async_get_entity_id(
        "switch", voip.DOMAIN, f"{voip_device.voip_id}-allow_call"
    )
    assert allowed_call_entity_id is not None
    state = hass.states.get(allowed_call_entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Allow calls
    hass.states.async_set(allowed_call_entity_id, STATE_ON)
    assert protocol.is_valid_call(call_info)


async def test_pre_recorded_message(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    call_info: CallInfo,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a pre-recorded message is played when calls aren't allowed."""
    assert await async_setup_component(hass, "voip", {})
    protocol: PreRecordMessageProtocol = make_protocol(hass, voip_devices, call_info)
    assert isinstance(protocol, PreRecordMessageProtocol)
    assert protocol.file_name == "problem.pcm"

    done = asyncio.Event()
    played_audio_bytes = b""

    def send_audio(audio_bytes: bytes, **kwargs):
        nonlocal played_audio_bytes

        # Should be problem.pcm from components/voip
        played_audio_bytes = audio_bytes
        done.set()

    protocol.transport = Mock()
    protocol.loop_delay = 0
    with patch.object(protocol, "send_audio", send_audio):
        protocol.on_chunk(bytes(_ONE_SECOND))

    async with asyncio.timeout(1):
        await done.wait()

    assert sum(played_audio_bytes) > 0
    assert played_audio_bytes == snapshot()


async def test_pipeline(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that pipeline function is called from RTP protocol."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)
    assert satellite.state == AssistSatelliteState.IDLE

    done = asyncio.Event()

    # Used to test that audio queue is cleared before pipeline starts
    bad_chunk = bytes([1, 2, 3, 4])

    async def async_pipeline_from_audio_stream(*args, device_id, **kwargs):
        assert device_id == voip_device.device_id

        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        in_command = False
        async for chunk in stt_stream:
            # Stream will end when VAD detects end of "speech"
            assert chunk != bad_chunk
            if sum(chunk) > 0:
                in_command = True
            elif in_command:
                break  # done with command

        assert satellite.state == AssistSatelliteState.LISTENING

        # Test empty data
        event_callback(
            assist_pipeline.PipelineEvent(
                type="not-used",
                data={},
            )
        )

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        assert satellite.state == AssistSatelliteState.PROCESSING

        # Fake intent result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_END,
                data={
                    "intent_output": {
                        "conversation_id": "fake-conversation",
                    }
                },
            )
        )

        # Proceed with media output
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"media_id": _MEDIA_ID}},
            )
        )

        assert satellite.state == AssistSatelliteState.RESPONDING

    def response_finished():
        done.set()

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        assert media_source_id == _MEDIA_ID
        return ("wav", _empty_wav())

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
        patch.object(satellite, "response_finished", response_finished),
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
            listening_tone_enabled=False,
            processing_tone_enabled=False,
            error_tone_enabled=False,
        )
        rtp_protocol.transport = Mock()

        # Ensure audio queue is cleared before pipeline starts
        rtp_protocol._audio_queue.put_nowait(bad_chunk)

        def send_audio(*args, **kwargs):
            # Don't send audio
            pass

        rtp_protocol.send_audio = Mock(side_effect=send_audio)

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(1):
            await done.wait()


async def test_stt_stream_timeout(
    hass: HomeAssistant, voip_devices: VoIPDevices, voip_device: VoIPDevice
) -> None:
    """Test timeout in STT stream during pipeline run."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        async for _chunk in stt_stream:
            # Iterate over stream
            pass

    with patch(
        "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
            audio_chunk_timeout=0.001,
            listening_tone_enabled=False,
            processing_tone_enabled=False,
            error_tone_enabled=False,
        )
        transport = Mock(spec=["close"])
        rtp_protocol.connection_made(transport)

        # Closing the transport will cause the test to succeed
        transport.close.side_effect = done.set

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to time out
        async with asyncio.timeout(1):
            await done.wait()


async def test_tts_timeout(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will time out based on its length."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        in_command = False
        async for chunk in stt_stream:
            if sum(chunk) > 0:
                in_command = True
            elif in_command:
                break  # done with command

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        # Fake intent result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_END,
                data={
                    "intent_output": {
                        "conversation_id": "fake-conversation",
                    }
                },
            )
        )

        # Proceed with media output
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"media_id": _MEDIA_ID}},
            )
        )

    tone_bytes = bytes([1, 2, 3, 4])

    async def async_send_audio(audio_bytes: bytes, **kwargs):
        if audio_bytes == tone_bytes:
            # Not TTS
            return

        # Block here to force a timeout in _send_tts
        await asyncio.sleep(2)

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        # Should time out immediately
        return ("wav", _empty_wav())

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
            tts_extra_timeout=0.001,
            listening_tone_enabled=True,
            processing_tone_enabled=True,
            error_tone_enabled=True,
        )
        rtp_protocol._tone_bytes = tone_bytes
        rtp_protocol._processing_bytes = tone_bytes
        rtp_protocol._error_bytes = tone_bytes
        rtp_protocol.transport = Mock()
        rtp_protocol.send_audio = Mock()

        original_send_tts = rtp_protocol._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(TimeoutError):
                await original_send_tts(*args, **kwargs)

            done.set()

        rtp_protocol._async_send_audio = AsyncMock(side_effect=async_send_audio)  # type: ignore[method-assign]
        rtp_protocol._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(1):
            await done.wait()


async def test_tts_wrong_extension(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will only stream WAV audio."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        in_command = False
        async for chunk in stt_stream:
            if sum(chunk) > 0:
                in_command = True
            elif in_command:
                break  # done with command

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        # Fake intent result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_END,
                data={
                    "intent_output": {
                        "conversation_id": "fake-conversation",
                    }
                },
            )
        )

        # Proceed with media output
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"media_id": _MEDIA_ID}},
            )
        )

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        # Should fail because it's not "wav"
        return ("mp3", b"")

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
        )
        rtp_protocol.transport = Mock()

        original_send_tts = rtp_protocol._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(ValueError):
                await original_send_tts(*args, **kwargs)

            done.set()

        rtp_protocol._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        rtp_protocol.on_chunk(bytes(_ONE_SECOND * 4))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(1):
            await done.wait()


async def test_tts_wrong_wav_format(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will only stream WAV audio with a specific format."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        in_command = False
        async for chunk in stt_stream:
            if sum(chunk) > 0:
                in_command = True
            elif in_command:
                break  # done with command

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        # Fake intent result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_END,
                data={
                    "intent_output": {
                        "conversation_id": "fake-conversation",
                    }
                },
            )
        )

        # Proceed with media output
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"media_id": _MEDIA_ID}},
            )
        )

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        # Should fail because it's not 16Khz, 16-bit mono
        with io.BytesIO() as wav_io:
            wav_file: wave.Wave_write = wave.open(wav_io, "wb")
            with wav_file:
                wav_file.setframerate(22050)
                wav_file.setsampwidth(2)
                wav_file.setnchannels(2)

            return ("wav", wav_io.getvalue())

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
            new=async_get_media_source_audio,
        ),
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
        )
        rtp_protocol.transport = Mock()

        original_send_tts = rtp_protocol._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(ValueError):
                await original_send_tts(*args, **kwargs)

            done.set()

        rtp_protocol._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        rtp_protocol.on_chunk(bytes(_ONE_SECOND * 4))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(1):
            await done.wait()


async def test_empty_tts_output(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will not stream when output is empty."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        in_command = False
        async for chunk in stt_stream:
            if sum(chunk) > 0:
                in_command = True
            elif in_command:
                break  # done with command

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        # Fake intent result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_END,
                data={
                    "intent_output": {
                        "conversation_id": "fake-conversation",
                    }
                },
            )
        )

        # Empty TTS output
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {}},
            )
        )

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.voip.PipelineRtpDatagramProtocol._send_tts",
        ) as mock_send_tts,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
        )
        rtp_protocol.transport = Mock()

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        rtp_protocol.on_chunk(bytes(_ONE_SECOND * 4))

        # Wait for mock pipeline to finish
        async with asyncio.timeout(1):
            await rtp_protocol._tts_done.wait()

        mock_send_tts.assert_not_called()


async def test_pipeline_error(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a pipeline error causes the error tone to be played."""
    assert await async_setup_component(hass, "voip", {})

    satellite = assist_satellite.async_get_satellite_entity(
        hass, voip.DOMAIN, voip_device.voip_id
    )
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()
    played_audio_bytes = b""

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        # Fake error
        event_callback = kwargs["event_callback"]
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.ERROR,
                data={"code": "error-code", "message": "error message"},
            )
        )

    async def async_send_audio(audio_bytes: bytes, **kwargs):
        nonlocal played_audio_bytes

        # Should be error.pcm from components/voip
        played_audio_bytes = audio_bytes
        done.set()

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            voip_devices,
            voip_device,
            satellite,
            Context(),
            opus_payload_type=123,
            listening_tone_enabled=False,
            processing_tone_enabled=False,
            error_tone_enabled=True,
        )
        rtp_protocol.transport = Mock()
        rtp_protocol._async_send_audio = AsyncMock(side_effect=async_send_audio)  # type: ignore[method-assign]

        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for error tone to be played
        async with asyncio.timeout(1):
            await done.wait()

        assert sum(played_audio_bytes) > 0
        assert played_audio_bytes == snapshot()
