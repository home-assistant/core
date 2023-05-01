"""Voice activity detection."""
from dataclasses import dataclass, field

import webrtcvad

_SAMPLE_RATE = 16000


@dataclass
class VoiceCommandSegmenter:
    """Segments an audio stream into voice commands using webrtcvad."""

    vad_mode: int = 3
    """Aggressiveness in filtering out non-speech. 3 is the most aggressive."""

    vad_frames: int = 480  # 30 ms
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
    _audio_buffer: bytes = field(default_factory=bytes)
    _bytes_per_chunk: int = 480 * 2  # 16-bit samples
    _seconds_per_chunk: float = 0.03  # 30 ms

    def __post_init__(self) -> None:
        """Initialize VAD."""
        self._vad = webrtcvad.Vad(self.vad_mode)
        self._bytes_per_chunk = self.vad_frames * 2
        self._seconds_per_chunk = self.vad_frames / _SAMPLE_RATE
        self.reset()

    def reset(self) -> None:
        """Reset all counters and state."""
        self._audio_buffer = b""
        self._speech_seconds_left = self.speech_seconds
        self._silence_seconds_left = self.silence_seconds
        self._timeout_seconds_left = self.timeout_seconds
        self._reset_seconds_left = self.reset_seconds
        self.in_command = False

    def process(self, samples: bytes) -> bool:
        """Process a 16-bit 16Khz mono audio samples.

        Returns False when command is done.
        """
        self._audio_buffer += samples

        # Process in 10, 20, or 30 ms chunks.
        num_chunks = len(self._audio_buffer) // self._bytes_per_chunk
        for chunk_idx in range(num_chunks):
            chunk_offset = chunk_idx * self._bytes_per_chunk
            chunk = self._audio_buffer[
                chunk_offset : chunk_offset + self._bytes_per_chunk
            ]
            if not self._process_chunk(chunk):
                self.reset()
                return False

        if num_chunks > 0:
            # Remove from buffer
            self._audio_buffer = self._audio_buffer[
                num_chunks * self._bytes_per_chunk :
            ]

        return True

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
        else:
            if not is_speech:
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
