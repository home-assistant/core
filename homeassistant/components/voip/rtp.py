import asyncio
import audioop
import logging

import opuslib

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_OPUS_RATE = 48000  # Hz
_OPUS_WIDTH = 2  # bytes
_OPUS_CHANNELS = 2  # stereo
_OPUS_FRAME_SIZE = 960  # 20 ms

_OUTPUT_RATE = 16000  # Hz


class RTPDatagramProtocol:
    def __init__(
        self,
        hass: HomeAssistant,
        audio_queue: "asyncio.Queue[bytes]",
    ):
        self.hass = hass
        self.transport = None
        self.dec = opuslib.api.decoder.create_state(_OPUS_RATE, _OPUS_CHANNELS)
        self.audio_queue = audio_queue

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            # Minimum header size
            assert len(data) >= 12, "Bad RTP header"

            # Assume no padding, extension headers, etc.
            opus_packet = data[12:]

            # Decode into raw audio
            audio_bytes = opuslib.api.decoder.decode(
                self.dec, opus_packet, len(opus_packet), _OPUS_FRAME_SIZE, False
            )

            # Convert from 48Khz stereo to 16Khz mono
            audio_bytes = audioop.tomono(audio_bytes, _OPUS_WIDTH, 1.0, 1.0)
            audio_bytes, _state = audioop.ratecv(
                audio_bytes, _OPUS_WIDTH, 1, _OPUS_RATE, _OUTPUT_RATE, None
            )

            self.audio_queue.put_nowait(audio_bytes)

        except Exception:
            _LOGGER.exception("datagram_received")
