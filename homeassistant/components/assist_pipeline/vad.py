"""Voice activity detection."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

import webrtcvad

_SAMPLE_RATE: Final = 16000  # Hz
_SAMPLE_WIDTH: Final = 2  # bytes


class VadSensitivity(StrEnum):
    """How quickly the end of a voice command is detected."""

    DEFAULT = "default"
    RELAXED = "relaxed"
    AGGRESSIVE = "aggressive"

    @staticmethod
    def to_seconds(sensitivity: VadSensitivity | str) -> float:
        """Return seconds of silence for sensitivity level."""
        sensitivity = VadSensitivity(sensitivity)
        if sensitivity == VadSensitivity.RELAXED:
            return 2.0

        if sensitivity == VadSensitivity.AGGRESSIVE:
            return 0.5

        return 1.0


class AudioBuffer:
    """Fixed-sized audio buffer with variable internal length."""

    def __init__(self, maxlen: int) -> None:
        """Initialize buffer."""
        self._buffer = bytearray(maxlen)
        self._length = 0

    @property
    def length(self) -> int:
        """Get number of bytes currently in the buffer."""
        return self._length

    def clear(self) -> None:
        """Clear the buffer."""
        self._length = 0

    def append(self, data: bytes) -> None:
        """Append bytes to the buffer, increasing the internal length."""
        data_len = len(data)
        if (self._length + data_len) > len(self._buffer):
            raise ValueError("Length cannot be greater than buffer size")

        self._buffer[self._length : self._length + data_len] = data
        self._length += data_len

    def bytes(self) -> bytes:
        """Convert written portion of buffer to bytes."""
        return bytes(self._buffer[: self._length])

    def __len__(self) -> int:
        """Get the number of bytes currently in the buffer."""
        return self._length

    def __bool__(self) -> bool:
        """Return True if there are bytes in the buffer."""
        return self._length > 0


@dataclass
class VoiceCommandSegmenter:
    """Segments an audio stream into voice commands using webrtcvad."""

    vad_mode: int = 3
    """Aggressiveness in filtering out non-speech. 3 is the most aggressive."""

    vad_samples_per_chunk: int = 480  # 30 ms
    """Must be 10, 20, or 30 ms at 16Khz."""

    speech_seconds: float = 0.3
    """Seconds of speech before voice command has started."""

    silence_seconds: float = 0.5
    """Seconds of silence after voice command has ended."""

    timeout_seconds: float = 15.0
    """Maximum number of seconds before stopping with timeout=True."""

    reset_seconds: float = 1.0
    """Seconds before reset start/stop time counters."""

    in_command: bool = False
    """True if inside voice command."""

    _speech_seconds_left: float = 0.0
    """Seconds left before considering voice command as started."""

    _silence_seconds_left: float = 0.0
    """Seconds left before considering voice command as stopped."""

    _timeout_seconds_left: float = 0.0
    """Seconds left before considering voice command timed out."""

    _reset_seconds_left: float = 0.0
    """Seconds left before resetting start/stop time counters."""

    _vad: webrtcvad.Vad = None
    _leftover_chunk_buffer: AudioBuffer = field(init=False)
    _bytes_per_chunk: int = field(init=False)
    _seconds_per_chunk: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize VAD."""
        self._vad = webrtcvad.Vad(self.vad_mode)
        self._bytes_per_chunk = self.vad_samples_per_chunk * _SAMPLE_WIDTH
        self._seconds_per_chunk = self.vad_samples_per_chunk / _SAMPLE_RATE
        self._leftover_chunk_buffer = AudioBuffer(
            self.vad_samples_per_chunk * _SAMPLE_WIDTH
        )
        self.reset()

    def reset(self) -> None:
        """Reset all counters and state."""
        self._leftover_chunk_buffer.clear()
        self._speech_seconds_left = self.speech_seconds
        self._silence_seconds_left = self.silence_seconds
        self._timeout_seconds_left = self.timeout_seconds
        self._reset_seconds_left = self.reset_seconds
        self.in_command = False

    def process(self, samples: bytes) -> bool:
        """Process 16-bit 16Khz mono audio samples.

        Returns False when command is done.
        """
        for chunk in chunk_samples(
            samples, self._bytes_per_chunk, self._leftover_chunk_buffer
        ):
            if not self._process_chunk(chunk):
                self.reset()
                return False

        return True

    @property
    def audio_buffer(self) -> bytes:
        """Get partial chunk in the audio buffer."""
        return self._leftover_chunk_buffer.bytes()

    def _process_chunk(self, chunk: bytes) -> bool:
        """Process a single chunk of 16-bit 16Khz mono audio.

        Returns False when command is done.
        """
        is_speech = self._vad.is_speech(chunk, _SAMPLE_RATE)

        self._timeout_seconds_left -= self._seconds_per_chunk
        if self._timeout_seconds_left <= 0:
            return False

        if not self.in_command:
            if is_speech:
                self._reset_seconds_left = self.reset_seconds
                self._speech_seconds_left -= self._seconds_per_chunk
                if self._speech_seconds_left <= 0:
                    # Inside voice command
                    self.in_command = True
            else:
                # Reset if enough silence
                self._reset_seconds_left -= self._seconds_per_chunk
                if self._reset_seconds_left <= 0:
                    self._speech_seconds_left = self.speech_seconds
        elif not is_speech:
            self._reset_seconds_left = self.reset_seconds
            self._silence_seconds_left -= self._seconds_per_chunk
            if self._silence_seconds_left <= 0:
                return False
        else:
            # Reset if enough speech
            self._reset_seconds_left -= self._seconds_per_chunk
            if self._reset_seconds_left <= 0:
                self._silence_seconds_left = self.silence_seconds

        return True


@dataclass
class VoiceActivityTimeout:
    """Detects silence in audio until a timeout is reached."""

    silence_seconds: float
    """Seconds of silence before timeout."""

    reset_seconds: float = 0.5
    """Seconds of speech before resetting timeout."""

    vad_mode: int = 3
    """Aggressiveness in filtering out non-speech. 3 is the most aggressive."""

    vad_samples_per_chunk: int = 480  # 30 ms
    """Must be 10, 20, or 30 ms at 16Khz."""

    _silence_seconds_left: float = 0.0
    """Seconds left before considering voice command as stopped."""

    _reset_seconds_left: float = 0.0
    """Seconds left before resetting start/stop time counters."""

    _vad: webrtcvad.Vad = None
    _leftover_chunk_buffer: AudioBuffer = field(init=False)
    _bytes_per_chunk: int = field(init=False)
    _seconds_per_chunk: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize VAD."""
        self._vad = webrtcvad.Vad(self.vad_mode)
        self._bytes_per_chunk = self.vad_samples_per_chunk * _SAMPLE_WIDTH
        self._seconds_per_chunk = self.vad_samples_per_chunk / _SAMPLE_RATE
        self._leftover_chunk_buffer = AudioBuffer(
            self.vad_samples_per_chunk * _SAMPLE_WIDTH
        )
        self.reset()

    def reset(self) -> None:
        """Reset all counters and state."""
        self._leftover_chunk_buffer.clear()
        self._silence_seconds_left = self.silence_seconds
        self._reset_seconds_left = self.reset_seconds

    def process(self, samples: bytes) -> bool:
        """Process 16-bit 16Khz mono audio samples.

        Returns False when timeout is reached.
        """
        for chunk in chunk_samples(
            samples, self._bytes_per_chunk, self._leftover_chunk_buffer
        ):
            if not self._process_chunk(chunk):
                return False

        return True

    def _process_chunk(self, chunk: bytes) -> bool:
        """Process a single chunk of 16-bit 16Khz mono audio.

        Returns False when timeout is reached.
        """
        if self._vad.is_speech(chunk, _SAMPLE_RATE):
            # Speech
            self._reset_seconds_left -= self._seconds_per_chunk
            if self._reset_seconds_left <= 0:
                # Reset timeout
                self._silence_seconds_left = self.silence_seconds
        else:
            # Silence
            self._silence_seconds_left -= self._seconds_per_chunk
            if self._silence_seconds_left <= 0:
                # Timeout reached
                return False

            # Slowly build reset counter back up
            self._reset_seconds_left = min(
                self.reset_seconds, self._reset_seconds_left + self._seconds_per_chunk
            )

        return True


def chunk_samples(
    samples: bytes,
    bytes_per_chunk: int,
    leftover_chunk_buffer: AudioBuffer,
) -> Iterable[bytes]:
    """Yield fixed-sized chunks from samples, keeping leftover bytes from previous call(s)."""

    if (len(leftover_chunk_buffer) + len(samples)) < bytes_per_chunk:
        # Extend leftover chunk, but not enough samples to complete it
        leftover_chunk_buffer.append(samples)
        return

    next_chunk_idx = 0

    if leftover_chunk_buffer:
        # Add to leftover chunk from previous call(s).
        bytes_to_copy = bytes_per_chunk - len(leftover_chunk_buffer)
        leftover_chunk_buffer.append(samples[:bytes_to_copy])
        next_chunk_idx = bytes_to_copy

        # Process full chunk in buffer
        yield leftover_chunk_buffer.bytes()
        leftover_chunk_buffer.clear()

    while next_chunk_idx < len(samples) - bytes_per_chunk + 1:
        # Process full chunk
        yield samples[next_chunk_idx : next_chunk_idx + bytes_per_chunk]
        next_chunk_idx += bytes_per_chunk

    # Capture leftover chunks
    if rest_samples := samples[next_chunk_idx:]:
        leftover_chunk_buffer.append(rest_samples)
