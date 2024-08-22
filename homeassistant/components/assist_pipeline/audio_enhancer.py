"""Audio enhancement for Assist."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

from pymicro_vad import MicroVad

from .const import BYTES_PER_CHUNK

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnhancedAudioChunk:
    """Enhanced audio chunk and metadata."""

    audio: bytes
    """Raw PCM audio @ 16Khz with 16-bit mono samples"""

    timestamp_ms: int
    """Timestamp relative to start of audio stream (milliseconds)"""

    is_speech: bool | None
    """True if audio chunk likely contains speech, False if not, None if unknown"""


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


class MicroVadEnhancer(AudioEnhancer):
    """Audio enhancer that just runs microVAD."""

    def __init__(
        self, auto_gain: int, noise_suppression: int, is_vad_enabled: bool
    ) -> None:
        """Initialize audio enhancer."""
        super().__init__(auto_gain, noise_suppression, is_vad_enabled)

        self.vad: MicroVad | None = None
        self.threshold = 0.5

        if self.is_vad_enabled:
            self.vad = MicroVad()
            _LOGGER.debug("Initialized microVAD with threshold=%s", self.threshold)

    def enhance_chunk(self, audio: bytes, timestamp_ms: int) -> EnhancedAudioChunk:
        """Enhance 10ms chunk of PCM audio @ 16Khz with 16-bit mono samples."""
        is_speech: bool | None = None

        if self.vad is not None:
            # Run VAD
            assert len(audio) == BYTES_PER_CHUNK
            speech_prob = self.vad.Process10ms(audio)
            is_speech = speech_prob > self.threshold

        return EnhancedAudioChunk(
            audio=audio, timestamp_ms=timestamp_ms, is_speech=is_speech
        )
