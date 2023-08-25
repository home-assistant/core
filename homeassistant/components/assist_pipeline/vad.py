"""Voice activity detection."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

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

    @length.setter
    def length(self, value: int) -> None:
        """Set the number of bytes in the buffer."""
        if value > len(self._buffer):
            raise ValueError("Length cannot be greater than buffer size")

        if value < 0:
            raise ValueError("Length cannot be negative")

        self._length = value

    def __len__(self) -> int:
        """Get the number of bytes currently in the buffer."""
        return self._length

    def __getitem__(self, item: Any) -> Any:
        """Get a slice of the buffer."""
        return self._buffer[item]

    def __setitem__(self, item: Any, value: Any) -> Any:
        """Set a slice of the buffer."""
        self._buffer[item] = value

    def __bytes__(self) -> bytes:
        """Convert written portion of buffer to bytes."""
        return bytes(self._buffer[: self._length])


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
    _sample_buffer: AudioBuffer = field(init=False)
    _bytes_per_chunk: int = field(init=False)
    _seconds_per_chunk: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize VAD."""
        self._vad = webrtcvad.Vad(self.vad_mode)
        self._bytes_per_chunk = self.vad_samples_per_chunk * _SAMPLE_WIDTH
        self._seconds_per_chunk = self.vad_samples_per_chunk / _SAMPLE_RATE
        self._sample_buffer = AudioBuffer(self.vad_samples_per_chunk * _SAMPLE_WIDTH)
        self.reset()

    def reset(self) -> None:
        """Reset all counters and state."""
        self._sample_buffer.length = 0
        self._speech_seconds_left = self.speech_seconds
        self._silence_seconds_left = self.silence_seconds
        self._timeout_seconds_left = self.timeout_seconds
        self._reset_seconds_left = self.reset_seconds
        self.in_command = False

    def process(self, samples: bytes) -> bool:
        """Process 16-bit 16Khz mono audio samples.

        Returns False when command is done.
        """
        for chunk in chunk_samples(samples, self._bytes_per_chunk, self._sample_buffer):
            if not self._process_chunk(chunk):
                self.reset()
                return False

        return True

    @property
    def audio_buffer(self) -> bytes:
        """Get partial chunk in the audio buffer."""
        return bytes(self._sample_buffer)

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
    _sample_buffer: AudioBuffer = field(init=False)
    _bytes_per_chunk: int = field(init=False)
    _seconds_per_chunk: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize VAD."""
        self._vad = webrtcvad.Vad(self.vad_mode)
        self._bytes_per_chunk = self.vad_samples_per_chunk * _SAMPLE_WIDTH
        self._seconds_per_chunk = self.vad_samples_per_chunk / _SAMPLE_RATE
        self._sample_buffer = AudioBuffer(self.vad_samples_per_chunk * _SAMPLE_WIDTH)
        self.reset()

    def reset(self) -> None:
        """Reset all counters and state."""
        self._sample_buffer.length = 0
        self._silence_seconds_left = self.silence_seconds
        self._reset_seconds_left = self.reset_seconds

    def process(self, samples: bytes) -> bool:
        """Process 16-bit 16Khz mono audio samples.

        Returns False when timeout is reached.
        """
        for chunk in chunk_samples(samples, self._bytes_per_chunk, self._sample_buffer):
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
    sample_buffer: AudioBuffer,
) -> Iterable[bytes]:
    """Yield fixed-sized chunks from samples, keeping leftover bytes in a buffer."""
    samples_offset = 0
    num_chunks_in_samples = len(samples) // bytes_per_chunk
    num_bytes_left = len(samples) % bytes_per_chunk

    if len(sample_buffer) > 0:
        # Add to partial chunk in buffer
        bytes_to_copy = min(num_bytes_left, bytes_per_chunk - len(sample_buffer))
        sample_buffer[len(sample_buffer) :] = samples[:bytes_to_copy]
        sample_buffer.length += bytes_to_copy
        samples_offset = bytes_to_copy
        num_bytes_left -= bytes_to_copy

    if len(sample_buffer) == bytes_per_chunk:
        # Process full chunk in buffer
        yield bytes(sample_buffer)
        sample_buffer.length = 0

    if num_bytes_left > 0:
        # Keep bytes at the end of samples for next chunk
        sample_buffer[:num_bytes_left] = samples[len(samples) - num_bytes_left :]
        sample_buffer.length = num_bytes_left

    # Process samples in chunks.
    for chunk_idx in range(num_chunks_in_samples):
        chunk_offset = samples_offset + (chunk_idx * bytes_per_chunk)
        chunk = samples[chunk_offset : chunk_offset + bytes_per_chunk]
        yield chunk

    return True
