"""UDP server for sending a media file as audio to an RTP client."""
import asyncio
import audioop
from collections.abc import Iterable
import logging
from pathlib import Path
import random
import struct
import wave

import opuslib

from homeassistant.core import HomeAssistant

_OPUS_RATE = 48000
_OPUS_WIDTH = 2
_OPUS_CHANNELS = 2
_OPUS_FRAME_SIZE = 960
_OPUS_PAYLOAD = 123

_OPUS_BYTES_PER_FRAME = _OPUS_FRAME_SIZE * _OPUS_WIDTH * _OPUS_CHANNELS

_LOGGER = logging.getLogger(__name__)


class MediaPlaybackDatagramProtocol(asyncio.DatagramProtocol):
    """Sends a WAV file as audio to an RTP client."""

    def __init__(
        self,
        hass: HomeAssistant,
        media_path: str | Path,
        silence_before: float = 0.5,
    ) -> None:
        self.hass = hass
        self.transport = None

        # Set up OPUS encoder for VoIP
        self.encoder = opuslib.api.encoder.create_state(
            _OPUS_RATE,
            _OPUS_WIDTH,
            opuslib.APPLICATION_VOIP,
        )
        opuslib.api.encoder.encoder_ctl(
            self.encoder,
            opuslib.api.ctl.set_signal,
            opuslib.SIGNAL_VOICE,
        )
        opuslib.api.encoder.encoder_ctl(
            self.encoder,
            opuslib.api.ctl.set_bandwidth,
            opuslib.BANDWIDTH_WIDEBAND,  # for 16Khz
        )
        opuslib.api.encoder.encoder_ctl(
            self.encoder,
            opuslib.api.ctl.set_bitrate,
            20_000,  # 16-20 kbit/s recommended for wideband
        )

        self.silence_before = silence_before
        self.media_path = Path(media_path)
        self._media_sent = False

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if self._media_sent:
            return

        self._media_sent = True
        self.hass.create_task(self._send_media(addr))

    async def _send_media(self, addr):
        flags = 0b10000000  # v2, no padding/extensions/CSRCs
        sequence_num = random.randint(0, 2**10)  # start from random offset
        timestamp = random.randint(1, 2**10)  # start from random timestep
        ssrc = random.randint(0, 2**32)  # unused

        sec_per_chunk = _OPUS_FRAME_SIZE / _OPUS_RATE

        # Wait before sending
        await asyncio.sleep(self.silence_before)

        with wave.open(str(self.media_path), "rb") as wav_file:
            for audio_bytes in _wav_to_chunks(wav_file, _OPUS_FRAME_SIZE):
                opus_bytes = opuslib.api.encoder.encode(
                    self.encoder,
                    audio_bytes,
                    _OPUS_FRAME_SIZE,
                    4000,  # recommended in opus docs
                )

                # See: https://en.wikipedia.org/wiki/Real-time_Transport_Protocol#Packet_header
                rtp_bytes = struct.pack(
                    ">BBHLL",
                    flags,
                    _OPUS_PAYLOAD,
                    sequence_num,
                    timestamp,
                    ssrc,
                )
                self.transport.sendto(rtp_bytes + opus_bytes, addr)
                sequence_num += 1
                timestamp += _OPUS_FRAME_SIZE

                # Wait almost the full amount of time for the chunk.
                #
                # Sending too fast will cause the phone to skip chunks,
                # since it doesn't seem to have a very large buffer.
                #
                # Sending too slow will cause audio artifacts if there is
                # network jitter, which is why programs like GStreamer are
                # much better at this.
                await asyncio.sleep(sec_per_chunk * 0.95)

        self.transport.close()


def _wav_to_chunks(wav_file: wave.Wave_read, samples_per_chunk: int) -> Iterable[bytes]:
    """Break WAV into fixed-sized chunks and resample."""
    original_rate = wav_file.getframerate()
    needs_resample = original_rate != _OPUS_RATE
    resample_state = None

    original_width = wav_file.getsampwidth()
    needs_resize = original_width != _OPUS_WIDTH

    original_channels = wav_file.getnchannels()
    needs_stereo = original_channels != _OPUS_CHANNELS

    audio_buffer = b""
    while audio_bytes := wav_file.readframes(samples_per_chunk):
        if needs_resample:
            # Convert to 48Khz
            audio_bytes, resample_state = audioop.ratecv(
                audio_bytes,
                original_width,
                original_channels,
                original_rate,
                _OPUS_RATE,
                resample_state,
            )

        if needs_resize:
            # Adjust sample width
            audio_bytes = audioop.lin2lin(
                audio_bytes,
                original_width,
                _OPUS_WIDTH,
            )

        if needs_stereo:
            # Convert to stereo
            audio_bytes = audioop.tostereo(
                audio_bytes,
                _OPUS_WIDTH,
                1.0,
                1.0,
            )

        audio_buffer += audio_bytes
        num_frames = len(audio_buffer) // _OPUS_BYTES_PER_FRAME

        # Yield chunks with *exactly* the desired number of frames
        for i in range(num_frames):
            offset = i * _OPUS_BYTES_PER_FRAME
            yield audio_buffer[offset : offset + _OPUS_BYTES_PER_FRAME]

        if num_frames > 0:
            # Remove audio already sent
            audio_buffer = audio_buffer[num_frames * _OPUS_BYTES_PER_FRAME :]

    # Yield remaining audio in buffer
    if audio_buffer:
        if len(audio_buffer) < _OPUS_BYTES_PER_FRAME:
            # Pad with silence
            audio_buffer += bytes(_OPUS_BYTES_PER_FRAME - len(audio_buffer))

        num_frames = len(audio_buffer) // _OPUS_BYTES_PER_FRAME

        # Yield chunks with *exactly* the desired number of frames
        for i in range(num_frames):
            offset = i * _OPUS_BYTES_PER_FRAME
            yield audio_buffer[offset : offset + _OPUS_BYTES_PER_FRAME]
