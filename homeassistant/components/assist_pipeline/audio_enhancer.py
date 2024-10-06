"""Audio enhancement for Assist."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

from pymicro_vad import MicroVad
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


class MicroVadSpeexEnhancer(AudioEnhancer):
    """Audio enhancer that runs microVAD and speex."""

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

        self.vad: MicroVad | None = None
        self.threshold = 0.5

        if self.is_vad_enabled:
            self.vad = MicroVad()
            _LOGGER.debug("Initialized microVAD with threshold=%s", self.threshold)

    def enhance_chunk(self, audio: bytes, timestamp_ms: int) -> EnhancedAudioChunk:
        """Enhance 10ms chunk of PCM audio @ 16Khz with 16-bit mono samples."""
        is_speech: bool | None = None

        assert len(audio) == BYTES_PER_CHUNK

        if self.vad is not None:
            # Run VAD
            speech_prob = self.vad.Process10ms(audio)
            is_speech = speech_prob > self.threshold

        if self.audio_processor is not None:
            # Run noise suppression and auto gain
            audio = self.audio_processor.Process10ms(audio).audio

        return EnhancedAudioChunk(
            audio=audio, timestamp_ms=timestamp_ms, is_speech=is_speech
        )
