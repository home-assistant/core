"""Utility for converting audio to/from RTP + OPUS packets."""
import audioop
import logging
from collections.abc import Iterable
from dataclasses import dataclass
import random
import struct
from typing import Any

import opuslib

_LOGGER = logging.getLogger(__name__)


@dataclass
class RtpOpusInput:
    """Extracts audio from RTP packets with OPUS."""

    opus_rate: int = 48000  # Hz
    opus_width: int = 2  # bytes
    opus_channels: int = 2
    opus_frame_size: int = 960  # samples per channel
    opus_payload: int = 123  # set by GrandStream

    def __post_init__(
        self,
    ) -> None:
        """Initialize encoder and state."""
        self._decoder = opuslib.api.decoder.create_state(
            self.opus_rate, self.opus_channels
        )

    def process_packet(
        self,
        rtp_bytes: bytes,
        rate: int,
        width: int,
        channels: int,
    ) -> bytes:
        """Extract, decode, and return raw audio from RTP packet."""
        if channels not in (1, 2):
            raise ValueError("Only mono and stereo audio is supported")

        # Minimum header size
        assert len(rtp_bytes) >= 12, "RTP packet is too small"

        # See: https://en.wikipedia.org/wiki/Real-time_Transport_Protocol#Packet_header
        flags, payload_type, _sequence_num, _timestamp, _ssrc = struct.unpack(
            ">BBHLL", rtp_bytes[:12]
        )

        assert flags == 0b10000000, "Padding and extension headers not supported"
        payload_type &= 0x80  # Remove marker bit
        assert (
            payload_type == self.opus_payload
        ), f"Expected payload type {self.opus_payload}, got {payload_type}"

        # Assume no padding, extension headers, etc.
        opus_bytes = rtp_bytes[12:]

        # Decode into raw audio.
        # This will always be 48Khz stereo with 16-bit samples.
        audio_bytes = opuslib.api.decoder.decode(
            self._decoder,
            opus_bytes,
            len(opus_bytes),
            self.opus_frame_size,
            False,  # no forward error correction (fec)
        )

        # Convert to target sample rate, etc.
        if channels == 1:
            # Convert to mono
            audio_bytes = audioop.tomono(
                audio_bytes,
                self.opus_width,
                1.0,
                1.0,
            )

        if rate != self.opus_rate:
            # Resample
            audio_bytes, _state = audioop.ratecv(
                audio_bytes,
                self.opus_width,
                channels,
                self.opus_rate,
                rate,
                None,
            )

        if width != self.opus_width:
            # Resize
            audio_bytes = audioop.lin2lin(
                audio_bytes,
                self.opus_width,
                width,
            )

        return audio_bytes


@dataclass
class RtpOpusOutput:
    """Prepares audio to send to an RTP client using OPUS."""

    opus_rate: int = 48000  # Hz
    opus_width: int = 2  # bytes
    opus_channels: int = 2
    opus_frame_size: int = 960  # samples per channel
    opus_payload: int = 123  # set by GrandStream
    opus_bytes_per_frame: int = 960 * 2 * 2

    _rtp_flags: int = 0b10000000  # v2, no padding/extensions/CSRCs
    _rtp_sequence_num: int = 0
    _rtp_timestamp: int = 0
    _rtp_ssrc: int = 0

    _encoder: opuslib.api.encoder.Encoder = None
    _audio_buffer: bytes = None  # type: ignore[assignment]
    _resample_state: Any = None

    def __post_init__(
        self,
    ) -> None:
        """Initialize encoder and state."""
        self.opus_bytes_per_frame = (
            self.opus_frame_size * self.opus_width * self.opus_channels
        )

        # Set up OPUS encoder for VoIP
        self._encoder = opuslib.api.encoder.create_state(
            self.opus_rate,
            self.opus_width,
            opuslib.APPLICATION_VOIP,
        )
        opuslib.api.encoder.encoder_ctl(
            self._encoder,
            opuslib.api.ctl.set_signal,
            opuslib.SIGNAL_VOICE,
        )
        opuslib.api.encoder.encoder_ctl(
            self._encoder,
            opuslib.api.ctl.set_bandwidth,
            opuslib.BANDWIDTH_WIDEBAND,  # for 16Khz
        )
        opuslib.api.encoder.encoder_ctl(
            self._encoder,
            opuslib.api.ctl.set_bitrate,
            20_000,  # 16-20 kbit/s recommended for wideband
        )

        self.reset()

    def reset(self):
        """Clear audio buffer and state."""
        self._audio_buffer = bytes()
        self._resample_state = None

        # Recommended to start from random offsets to aid encryption
        self._rtp_sequence_num = random.randint(0, 2**10)
        self._rtp_timestamp = random.randint(1, 2**10)

        # Change each time
        self._rtp_ssrc = random.randint(0, 2**32)

    def process_audio(
        self,
        audio_bytes: bytes,
        rate: int,
        width: int,
        channels: int,
        is_end: bool = False,
    ) -> Iterable[bytes]:
        """Process a chunk of raw audio and yield RTP packet(s)."""
        if rate != self.opus_rate:
            # Convert to 48Khz
            audio_bytes, self._resample_state = audioop.ratecv(
                audio_bytes,
                width,
                channels,
                rate,
                self.opus_rate,
                self._resample_state,
            )

        if width != self.opus_width:
            # Adjust sample width
            audio_bytes = audioop.lin2lin(
                audio_bytes,
                width,
                self.opus_width,
            )

        if channels != self.opus_channels:
            # Convert to stereo
            audio_bytes = audioop.tostereo(
                audio_bytes,
                self.opus_width,
                1.0,
                1.0,
            )

        self._audio_buffer += audio_bytes
        if is_end:
            # Pad with silence
            bytes_missing = len(self._audio_buffer) % self.opus_bytes_per_frame
            if bytes_missing > 0:
                self._audio_buffer += bytes(bytes_missing)

        num_frames = len(self._audio_buffer) // self.opus_bytes_per_frame

        # Process chunks with *exactly* the desired number of frames
        for i in range(num_frames):
            offset = i * self.opus_bytes_per_frame
            audio_chunk = self._audio_buffer[
                offset : offset + self.opus_bytes_per_frame
            ]

            # Encode to OPUS packet
            opus_bytes = opuslib.api.encoder.encode(
                self._encoder,
                audio_chunk,
                self.opus_frame_size,
                4000,  # recommended in opus docs
            )

            # Add RTP header
            # See: https://en.wikipedia.org/wiki/Real-time_Transport_Protocol#Packet_header
            rtp_bytes = struct.pack(
                ">BBHLL",
                self._rtp_flags,
                self.opus_payload,
                self._rtp_sequence_num,
                self._rtp_timestamp,
                self._rtp_ssrc,
            )

            # RTP packet
            yield rtp_bytes + opus_bytes

            # Next frame
            self._rtp_sequence_num += 1
            self._rtp_timestamp += self.opus_frame_size

        if num_frames > 0:
            # Remove audio already sent
            self._audio_buffer = self._audio_buffer[
                num_frames * self.opus_bytes_per_frame :
            ]

        if is_end:
            # Clear audio buffer and state
            self.reset()
