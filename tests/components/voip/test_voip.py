"""Test VoIP protocol."""
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import async_timeout

from homeassistant.components import assist_pipeline, voip
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit
_MEDIA_ID = "12345"


async def test_pipeline(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
) -> None:
    """Test that pipeline function is called from RTP protocol."""
    assert await async_setup_component(hass, "voip", {})

    def is_speech(self, chunk, sample_rate):
        """Anything non-zero is speech."""
        return sum(chunk) > 0

    done = asyncio.Event()

    # Used to test that audio queue is cleared before pipeline starts
    bad_chunk = bytes([1, 2, 3, 4])

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        async for _chunk in stt_stream:
            # Stream will end when VAD detects end of "speech"
            assert _chunk != bad_chunk

        # Test empty data
        event_callback(
            assist_pipeline.PipelineEvent(
                type="not-used",
                data={},
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
        assert media_source_id == _MEDIA_ID

        return ("mp3", b"")

    with patch(
        "webrtcvad.Vad.is_speech",
        new=is_speech,
    ), patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ), patch(
        "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
        new=async_get_media_source_audio,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            hass.config.language,
            voip_device,
            Context(),
            listening_tone_enabled=False,
            processing_tone_enabled=False,
        )
        rtp_protocol.transport = Mock()

        # Ensure audio queue is cleared before pipeline starts
        rtp_protocol._audio_queue.put_nowait(bad_chunk)

        def send_audio(*args, **kwargs):
            # Test finished successfully
            done.set()

        rtp_protocol.send_audio = Mock(side_effect=send_audio)

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with async_timeout.timeout(1):
            await done.wait()


async def test_pipeline_timeout(hass: HomeAssistant, voip_device: VoIPDevice) -> None:
    """Test timeout during pipeline run."""
    assert await async_setup_component(hass, "voip", {})

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        await asyncio.sleep(10)

    with patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ), patch(
        "homeassistant.components.voip.voip.PipelineRtpDatagramProtocol._wait_for_speech",
        return_value=True,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            hass.config.language,
            voip_device,
            Context(),
            pipeline_timeout=0.001,
            listening_tone_enabled=False,
            processing_tone_enabled=False,
        )
        transport = Mock(spec=["close"])
        rtp_protocol.connection_made(transport)

        # Closing the transport will cause the test to succeed
        transport.close.side_effect = done.set

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to time out
        async with async_timeout.timeout(1):
            await done.wait()


async def test_stt_stream_timeout(hass: HomeAssistant, voip_device: VoIPDevice) -> None:
    """Test timeout in STT stream during pipeline run."""
    assert await async_setup_component(hass, "voip", {})

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        async for _chunk in stt_stream:
            # Iterate over stream
            pass

    with patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            hass.config.language,
            voip_device,
            Context(),
            audio_timeout=0.001,
            listening_tone_enabled=False,
            processing_tone_enabled=False,
        )
        transport = Mock(spec=["close"])
        rtp_protocol.connection_made(transport)

        # Closing the transport will cause the test to succeed
        transport.close.side_effect = done.set

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to time out
        async with async_timeout.timeout(1):
            await done.wait()


async def test_tts_timeout(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
) -> None:
    """Test that TTS will time out based on its length."""
    assert await async_setup_component(hass, "voip", {})

    def is_speech(self, chunk, sample_rate):
        """Anything non-zero is speech."""
        return sum(chunk) > 0

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        stt_stream = kwargs["stt_stream"]
        event_callback = kwargs["event_callback"]
        async for _chunk in stt_stream:
            # Stream will end when VAD detects end of "speech"
            pass

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

    def send_audio(*args, **kwargs):
        # Block here to force a timeout in _send_tts
        time.sleep(1)

    async def async_get_media_source_audio(
        hass: HomeAssistant,
        media_source_id: str,
    ) -> tuple[str, bytes]:
        # Should time out immediately
        return ("raw", bytes(0))

    with patch(
        "webrtcvad.Vad.is_speech",
        new=is_speech,
    ), patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ), patch(
        "homeassistant.components.voip.voip.tts.async_get_media_source_audio",
        new=async_get_media_source_audio,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            hass.config.language,
            voip_device,
            Context(),
            listening_tone_enabled=False,
            processing_tone_enabled=False,
        )
        rtp_protocol.transport = Mock()
        rtp_protocol.send_audio = Mock(side_effect=send_audio)

        async def send_tts(*args, **kwargs):
            # Call original then end test successfully
            rtp_protocol._send_tts(*args, **kwargs)
            done.set()

        rtp_protocol._send_tts = AsyncMock(side_effect=send_tts)

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with async_timeout.timeout(1):
            await done.wait()
