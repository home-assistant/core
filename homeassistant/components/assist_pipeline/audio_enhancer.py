"""Audio enhancement for Assist."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import math

from pysilero_vad import SileroVoiceActivityDetector
from pyspeex_noise import AudioProcessor

from .const import BYTES_PER_CHUNK

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnhancedAudioChunk:
    """Enhanced audio chunk and metadata."""

    audio: bytes
    """Raw PCM audio @ 16Khz with 16-bit mono samples"""

    timestamp_ms: int
    """Timestamp relative to start of audio stream (milliseconds)"""

    speech_probability: float | None
    """Probability that audio chunk contains speech (0-1), None if unknown"""


class AudioEnhancer(ABC):
    """Base class for audio enhancement."""

    def __init__(
        self, auto_gain: int, noise_suppression: int, is_vad_enabled: bool
    ) -> None:
        """Initialize audio enhancer."""
        self.auto_gain = auto_gain
        self.noise_suppression = noise_suppression
        self.is_vad_enabled = is_vad_enabled

    @abstractmethod
    def enhance_chunk(self, audio: bytes, timestamp_ms: int) -> EnhancedAudioChunk:
        """Enhance chunk of PCM audio @ 16Khz with 16-bit mono samples."""


class SileroVadSpeexEnhancer(AudioEnhancer):
    """Audio enhancer that runs Silero VAD and speex."""

    def __init__(
        self, auto_gain: int, noise_suppression: int, is_vad_enabled: bool
    ) -> None:
        """Initialize audio enhancer."""
        super().__init__(auto_gain, noise_suppression, is_vad_enabled)

        self.audio_processor: AudioProcessor | None = None

        # Scale from 0-4
        self.noise_suppression = noise_suppression * -15

        # Scale from 0-31
        self.auto_gain = auto_gain * 300

        if (self.auto_gain != 0) or (self.noise_suppression != 0):
            self.audio_processor = AudioProcessor(
                self.auto_gain, self.noise_suppression
            )
            _LOGGER.debug(
                "Initialized speex with auto_gain=%s, noise_suppression=%s",
                self.auto_gain,
                self.noise_suppression,
            )

        self.vad: SileroVoiceActivityDetector | None = None

        # We get 10ms chunks but Silero works on 32ms chunks, so we have to
        # buffer audio. The previous speech probability is used until enough
        # audio has been buffered.
        self._vad_buffer: bytearray | None = None
        self._vad_buffer_chunks = 0
        self._vad_buffer_chunk_idx = 0
        self._last_speech_probability: float | None = None

        if self.is_vad_enabled:
            self.vad = SileroVoiceActivityDetector()

            # VAD buffer is a multiple of 10ms, but Silero VAD needs 32ms.
            self._vad_buffer_chunks = int(
                math.ceil(self.vad.chunk_bytes() / BYTES_PER_CHUNK)
            )
            self._vad_leftover_bytes = self.vad.chunk_bytes() - BYTES_PER_CHUNK
            self._vad_buffer = bytearray(self.vad.chunk_bytes())
            _LOGGER.debug("Initialized Silero VAD")

    def enhance_chunk(self, audio: bytes, timestamp_ms: int) -> EnhancedAudioChunk:
        """Enhance 10ms chunk of PCM audio @ 16Khz with 16-bit mono samples."""
        assert len(audio) == BYTES_PER_CHUNK

        if self.vad is not None:
            # Run VAD
            assert self._vad_buffer is not None
            start_idx = self._vad_buffer_chunk_idx * BYTES_PER_CHUNK
            self._vad_buffer[start_idx : start_idx + BYTES_PER_CHUNK] = audio

            self._vad_buffer_chunk_idx += 1
            if self._vad_buffer_chunk_idx >= self._vad_buffer_chunks:
                # We have enough data to run Silero VAD (32 ms)
                self._last_speech_probability = self.vad.process_chunk(
                    self._vad_buffer[: self.vad.chunk_bytes()]
                )

                # Copy leftover audio that wasn't processed to start
                self._vad_buffer[: self._vad_leftover_bytes] = self._vad_buffer[
                    -self._vad_leftover_bytes :
                ]
                self._vad_buffer_chunk_idx = 0

        if self.audio_processor is not None:
            # Run noise suppression and auto gain
            audio = self.audio_processor.Process10ms(audio).audio

        return EnhancedAudioChunk(
            audio=audio,
            timestamp_ms=timestamp_ms,
            speech_probability=self._last_speech_probability,
        )
