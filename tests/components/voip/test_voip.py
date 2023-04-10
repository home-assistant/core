"""Test Voice Assistant init."""
import asyncio
from unittest.mock import Mock, patch

import async_timeout

from homeassistant.components import voice_assistant, voip
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit
_MEDIA_ID = "12345"


async def test_rtp_protocol(hass: HomeAssistant) -> None:
    """Test that pipeline function is called from RTP protocol."""
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

        # Proceed with media output
        event_callback(
            voice_assistant.PipelineEvent(
                type=voice_assistant.PipelineEventType.TTS_END,
                data={"tts_output": {"media_id": _MEDIA_ID}},
            )
        )

    with patch(
        "webrtcvad.Vad.is_speech",
        new=is_speech,
    ), patch(
        "homeassistant.components.voip.voip.async_pipeline_from_audio_stream",
        new=async_pipeline_from_audio_stream,
    ):
        rtp_protocol = voip.voip.PipelineRtpDatagramProtocol(
            hass,
            hass.config.language,
        )

        async def _send_media(media_id: str):
            assert media_id == _MEDIA_ID

            # Test finished successfully
            done.set()

        rtp_protocol._send_media = Mock(  # type: ignore[assignment]
            side_effect=_send_media
        )

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # "speech"
        rtp_protocol.on_chunk(bytes([255] * _ONE_SECOND * 2))

        # silence
        rtp_protocol.on_chunk(bytes(_ONE_SECOND))

        # Wait for mock pipeline to exhaust the audio stream
        async with async_timeout.timeout(1):
            await done.wait()
