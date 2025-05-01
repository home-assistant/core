"""Test VoIP protocol."""

import asyncio
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
import wave

import pytest
from syrupy.assertion import SnapshotAssertion
from voip_utils import CallInfo

from homeassistant.components import assist_pipeline, assist_satellite, tts, voip
from homeassistant.components.assist_satellite import AssistSatelliteEntity

# pylint: disable-next=hass-component-root-import
from homeassistant.components.assist_satellite.entity import AssistSatelliteState
from homeassistant.components.voip import DOMAIN, HassVoipDatagramProtocol
from homeassistant.components.voip.assist_satellite import Tones, VoipAssistSatellite
from homeassistant.components.voip.devices import VoIPDevice, VoIPDevices
from homeassistant.components.voip.voip import PreRecordMessageProtocol, make_protocol
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_setup_component

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit
_MEDIA_ID = "12345"


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


def _empty_wav(framerate=16000) -> bytes:
    """Return bytes of an empty WAV file."""
    with io.BytesIO() as wav_io:
        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        with wav_file:
            wav_file.setframerate(framerate)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)

        return wav_io.getvalue()


def async_get_satellite_entity(
    hass: HomeAssistant, domain: str, unique_id_prefix: str
) -> AssistSatelliteEntity | None:
    """Get Assist satellite entity."""
    ent_reg = er.async_get(hass)
    satellite_entity_id = ent_reg.async_get_entity_id(
        Platform.ASSIST_SATELLITE, domain, f"{unique_id_prefix}-assist_satellite"
    )
    if satellite_entity_id is None:
        return None
    assert not satellite_entity_id.endswith("none")

    component: EntityComponent[AssistSatelliteEntity] = hass.data[
        assist_satellite.DOMAIN
    ]
    return component.get_entity(satellite_entity_id)


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


async def test_calls_not_allowed(
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

    # Test the playback
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
    assert played_audio_bytes == snapshot


async def test_pipeline_not_found(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    call_info: CallInfo,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a pre-recorded message is played when a pipeline isn't found."""
    assert await async_setup_component(hass, "voip", {})

    with patch(
        "homeassistant.components.voip.voip.async_get_pipeline", return_value=None
    ):
        protocol: PreRecordMessageProtocol = make_protocol(
            hass, voip_devices, call_info
        )

    assert isinstance(protocol, PreRecordMessageProtocol)
    assert protocol.file_name == "problem.pcm"


async def test_satellite_prepared(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    call_info: CallInfo,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that satellite is prepared for a call."""
    assert await async_setup_component(hass, "voip", {})

    pipeline = assist_pipeline.Pipeline(
        conversation_engine="test",
        conversation_language="en",
        language="en",
        name="test",
        stt_engine="test",
        stt_language="en",
        tts_engine="test",
        tts_language="en",
        tts_voice=None,
        wake_word_entity=None,
        wake_word_id=None,
    )

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)

    with (
        patch(
            "homeassistant.components.voip.voip.async_get_pipeline",
            return_value=pipeline,
        ),
    ):
        protocol = make_protocol(hass, voip_devices, call_info)
        assert protocol == satellite


async def test_pipeline(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    call_info: CallInfo,
) -> None:
    """Test that pipeline function is called from RTP protocol."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)
    voip_user_id = satellite.config_entry.data["user"]
    assert voip_user_id

    # Satellite is muted until a call begins
    assert satellite.state == AssistSatelliteState.IDLE

    done = asyncio.Event()

    # Used to test that audio queue is cleared before pipeline starts
    bad_chunk = bytes([1, 2, 3, 4])

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context: Context,
        *args,
        device_id: str | None,
        tts_audio_output: str | dict[str, Any] | None,
        **kwargs,
    ):
        assert context.user_id == voip_user_id
        assert device_id == voip_device.device_id

        # voip can only stream WAV
        assert tts_audio_output == {
            tts.ATTR_PREFERRED_FORMAT: "wav",
            tts.ATTR_PREFERRED_SAMPLE_RATE: 16000,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1,
            tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
        }

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

        # Test empty data
        event_callback(
            assist_pipeline.PipelineEvent(
                type="not-used",
                data={},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_START,
                data={"engine": "test", "metadata": {}},
            )
        )

        assert satellite.state == AssistSatelliteState.LISTENING

        # Fake STT result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.STT_END,
                data={"stt_output": {"text": "fake-text"}},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.INTENT_START,
                data={
                    "engine": "test",
                    "language": hass.config.language,
                    "intent_input": "fake-text",
                    "conversation_id": None,
                    "device_id": None,
                },
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

        # Fake tts result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_START,
                data={
                    "engine": "test",
                    "language": hass.config.language,
                    "voice": "test",
                    "tts_input": "fake-text",
                },
            )
        )

        assert satellite.state == AssistSatelliteState.RESPONDING

        # Proceed with media output
        mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"token": mock_tts_result_stream.token}},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.RUN_END
            )
        )

    original_tts_response_finished = satellite.tts_response_finished

    def tts_response_finished():
        original_tts_response_finished()
        done.set()

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch.object(satellite, "tts_response_finished", tts_response_finished),
    ):
        satellite._tones = Tones(0)
        satellite.connection_made(Mock())

        assert satellite.state == AssistSatelliteState.IDLE

        # Ensure audio queue is cleared before pipeline starts
        satellite._audio_queue.put_nowait(bad_chunk)

        def send_audio(*args, **kwargs):
            # Don't send audio
            pass

        satellite.send_audio = Mock(side_effect=send_audio)

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        satellite.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(1):
            await done.wait()

        # Finished speaking
        assert satellite.state == AssistSatelliteState.IDLE


async def test_stt_stream_timeout(
    hass: HomeAssistant, voip_devices: VoIPDevices, voip_device: VoIPDevice
) -> None:
    """Test timeout in STT stream during pipeline run."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        async for _chunk in stt_stream:
            # Iterate over stream
            pass

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        satellite._tones = Tones(0)
        satellite._audio_chunk_timeout = 0.001
        transport = Mock(spec=["close"])
        satellite.connection_made(transport)

        # Closing the transport will cause the test to succeed
        transport.close.side_effect = done.set

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

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

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
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
        mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"token": mock_tts_result_stream.token}},
            )
        )

    tone_bytes = bytes([1, 2, 3, 4])

    async def async_send_audio(audio_bytes: bytes, **kwargs):
        if audio_bytes == tone_bytes:
            # Not TTS
            return

        # Block here to force a timeout in _send_tts
        await asyncio.sleep(2)

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        satellite._tts_extra_timeout = 0.001
        for tone in Tones:
            satellite._tone_bytes[tone] = tone_bytes

        satellite.connection_made(Mock())
        satellite.send_audio = Mock()

        original_send_tts = satellite._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(TimeoutError):
                await original_send_tts(*args, **kwargs)

            done.set()

        satellite._async_send_audio = AsyncMock(side_effect=async_send_audio)  # type: ignore[method-assign]
        satellite._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        satellite.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

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

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    satellite.addr = ("192.168.1.1", 12345)
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
        # Should fail because it's not "wav"
        mock_tts_result_stream = MockResultStream(hass, "mp3", b"")
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"token": mock_tts_result_stream.token}},
            )
        )

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        original_send_tts = satellite._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(ValueError):
                await original_send_tts(*args, **kwargs)

            done.set()

        satellite._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        satellite.connection_made(Mock())

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        satellite.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(3):
            await done.wait()


async def test_tts_wrong_wav_format(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will only stream WAV audio with a specific format."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    satellite.addr = ("192.168.1.1", 12345)
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
        # Should fail because it's not 16Khz
        mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav(22050))
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"token": mock_tts_result_stream.token}},
            )
        )

    with patch(
        "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        original_send_tts = satellite._send_tts

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            with pytest.raises(ValueError):
                await original_send_tts(*args, **kwargs)

            done.set()

        satellite._send_tts = AsyncMock(side_effect=send_tts)  # type: ignore[method-assign]

        satellite.connection_made(Mock())

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        satellite.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with asyncio.timeout(3):
            await done.wait()


async def test_empty_tts_output(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will not stream when output is empty."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    satellite.addr = ("192.168.1.1", 12345)
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
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite._send_tts",
        ) as mock_send_tts,
    ):
        satellite.connection_made(Mock())

        # silence
        satellite.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        satellite.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence (assumes relaxed VAD sensitivity)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to finish
        async with asyncio.timeout(2):
            await satellite._tts_done.wait()

        mock_send_tts.assert_not_called()


async def test_pipeline_error(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a pipeline error causes the error tone to be played."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
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
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
    ):
        satellite._tones = Tones.ERROR
        satellite.connection_made(Mock())
        satellite._async_send_audio = AsyncMock(side_effect=async_send_audio)  # type: ignore[method-assign]

        satellite.on_chunk(bytes(_ONE_SECOND))

        # Wait for error tone to be played
        async with asyncio.timeout(1):
            await done.wait()

        assert sum(played_audio_bytes) > 0
        assert played_audio_bytes == snapshot


@pytest.mark.usefixtures("socket_enabled")
async def test_announce(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test announcement."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)
    assert (
        satellite.supported_features
        & assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "assist_satellite",
            "announce",
            service_data={"media_id": "http://example.com"},
            blocking=True,
            target={
                "entity_id": satellite.entity_id,
            },
        )
    assert err.value.translation_domain == "voip"
    assert err.value.translation_key == "non_tts_announcement"

    mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
    announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test announcement",
        media_id=_MEDIA_ID,
        tts_token=mock_tts_result_stream.token,
        original_media_id=_MEDIA_ID,
        media_id_source="tts",
    )

    # Protocol has already been mocked, but "outgoing_call" is not async
    mock_protocol: AsyncMock = hass.data[DOMAIN].protocol
    mock_protocol.outgoing_call = Mock()

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite._send_tts",
        ) as mock_send_tts,
    ):
        announce_task = hass.async_create_background_task(
            satellite.async_announce(announcement), "voip_announce"
        )
        await asyncio.sleep(0)
        satellite.connection_made(Mock())
        mock_protocol.outgoing_call.assert_called_once()

        # Trigger announcement
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        async with asyncio.timeout(2):
            await announce_task

        mock_send_tts.assert_called_once_with(
            mock_tts_result_stream, wait_for_tone=False
        )


@pytest.mark.usefixtures("socket_enabled")
async def test_voip_id_is_ip_address(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test announcement when VoIP is an IP address instead of a SIP header."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)
    assert (
        satellite.supported_features
        & assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
    )

    mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
    announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test announcement",
        media_id=_MEDIA_ID,
        tts_token=mock_tts_result_stream.token,
        original_media_id=_MEDIA_ID,
        media_id_source="tts",
    )

    # Protocol has already been mocked, but "outgoing_call" is not async
    mock_protocol: AsyncMock = hass.data[DOMAIN].protocol
    mock_protocol.outgoing_call = Mock()

    with (
        patch.object(voip_device, "voip_id", "192.168.68.10"),
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite._send_tts",
        ) as mock_send_tts,
    ):
        announce_task = hass.async_create_background_task(
            satellite.async_announce(announcement), "voip_announce"
        )
        await asyncio.sleep(0)
        satellite.connection_made(Mock())
        mock_protocol.outgoing_call.assert_called_once()
        assert (
            mock_protocol.outgoing_call.call_args.kwargs["destination"].host
            == "192.168.68.10"
        )

        # Trigger announcement
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        async with asyncio.timeout(2):
            await announce_task

        mock_send_tts.assert_called_once_with(
            mock_tts_result_stream, wait_for_tone=False
        )


@pytest.mark.usefixtures("socket_enabled")
async def test_announce_timeout(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test announcement when user does not pick up the phone in time."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)
    assert (
        satellite.supported_features
        & assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
    )

    mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
    announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test announcement",
        media_id=_MEDIA_ID,
        tts_token=mock_tts_result_stream.token,
        original_media_id=_MEDIA_ID,
        media_id_source="tts",
    )

    # Protocol has already been mocked, but some methods are not async
    mock_protocol: AsyncMock = hass.data[DOMAIN].protocol
    mock_protocol.outgoing_call = Mock()
    mock_protocol.cancel_call = Mock()

    # Very short timeout which will trigger because we don't send any audio in
    with (
        patch(
            "homeassistant.components.voip.assist_satellite._ANNOUNCEMENT_RING_TIMEOUT",
            0.01,
        ),
    ):
        satellite.connection_made(Mock())
        with pytest.raises(TimeoutError):
            await satellite.async_announce(announcement)


@pytest.mark.usefixtures("socket_enabled")
async def test_start_conversation(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test start conversation."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)
    assert (
        satellite.supported_features
        & assist_satellite.AssistSatelliteEntityFeature.START_CONVERSATION
    )

    mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
    announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test announcement",
        media_id=_MEDIA_ID,
        tts_token=mock_tts_result_stream.token,
        original_media_id=_MEDIA_ID,
        media_id_source="tts",
    )

    # Protocol has already been mocked, but "outgoing_call" is not async
    mock_protocol: AsyncMock = hass.data[DOMAIN].protocol
    mock_protocol.outgoing_call = Mock()

    tts_sent = asyncio.Event()

    async def _send_tts(*args, **kwargs):
        tts_sent.set()

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context: Context,
        *args,
        device_id: str | None,
        tts_audio_output: str | dict[str, Any] | None,
        **kwargs,
    ):
        event_callback = kwargs["event_callback"]

        # Fake tts result
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_START,
                data={
                    "engine": "test",
                    "language": hass.config.language,
                    "voice": "test",
                    "tts_input": "fake-text",
                },
            )
        )

        # Proceed with media output
        mock_tts_result_stream = MockResultStream(hass, "wav", _empty_wav())
        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.TTS_END,
                data={"tts_output": {"token": mock_tts_result_stream.token}},
            )
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                type=assist_pipeline.PipelineEventType.RUN_END
            )
        )

    with (
        patch(
            "homeassistant.components.voip.assist_satellite.VoipAssistSatellite._send_tts",
            new=_send_tts,
        ),
        patch(
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
            new=async_pipeline_from_audio_stream,
        ),
    ):
        satellite.connection_made(Mock())
        conversation_task = hass.async_create_background_task(
            satellite.async_start_conversation(announcement), "voip_start_conversation"
        )
        await asyncio.sleep(0)
        mock_protocol.outgoing_call.assert_called_once()

        # Trigger announcement and wait for it to finish
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        async with asyncio.timeout(2):
            await tts_sent.wait()

        # Trigger pipeline
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(0.2)
        satellite.on_chunk(bytes(_ONE_SECOND))
        await asyncio.sleep(3)
        async with asyncio.timeout(3):
            # Wait for Conversation end
            await conversation_task


@pytest.mark.usefixtures("socket_enabled")
async def test_start_conversation_user_doesnt_pick_up(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    voip_device: VoIPDevice,
) -> None:
    """Test start conversation when the user doesn't pick up."""
    assert await async_setup_component(hass, "voip", {})

    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    satellite.addr = ("192.168.1.1", 12345)
    assert isinstance(satellite, VoipAssistSatellite)
    assert (
        satellite.supported_features
        & assist_satellite.AssistSatelliteEntityFeature.START_CONVERSATION
    )

    # Protocol has already been mocked, but "outgoing_call" is not async
    mock_protocol: AsyncMock = hass.data[DOMAIN].protocol
    mock_protocol.outgoing_call = Mock()

    announcement = assist_satellite.AssistSatelliteAnnouncement(
        message="test announcement",
        media_id=_MEDIA_ID,
        tts_token="test-token",
        original_media_id=_MEDIA_ID,
        media_id_source="tts",
    )

    # Very short timeout which will trigger because we don't send any audio in
    with (
        patch(
            "homeassistant.components.voip.assist_satellite._ANNOUNCEMENT_RING_TIMEOUT",
            0.1,
        ),
    ):
        satellite.connection_made(Mock())

        with pytest.raises(TimeoutError):
            await satellite.async_start_conversation(announcement)
