"""Test VoIP protocol."""
import asyncio
from unittest.mock import Mock, patch

import async_timeout

from homeassistant.components import assist_pipeline, voip
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit
_MEDIA_ID = "12345"


async def test_pipeline(hass: HomeAssistant) -> None:
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
            pass

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
        )
        rtp_protocol.transport = Mock()

        # Ensure audio queue is cleared before pipeline starts
        rtp_protocol._audio_queue.put_nowait(bad_chunk)

        async def send_audio(*args, **kwargs):
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


async def test_pipeline_timeout(hass: HomeAssistant) -> None:
    """Test timeout during pipeline run."""
    assert await async_setup_component(hass, "voip", {})

    done = asyncio.Event()

    async def async_pipeline_from_audio_stream(*args, **kwargs):
        await asyncio.sleep(10)

    with patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass, hass.config.language, pipeline_timeout=0.001
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


async def test_stt_stream_timeout(hass: HomeAssistant) -> None:
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
            hass, hass.config.language, audio_timeout=0.001
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
