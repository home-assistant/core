"""Speech-to-text data models."""

from dataclasses import dataclass

from .const import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResultState,
)


@dataclass
class SpeechMetadata:
    """Metadata of audio stream."""

    language: str
    format: AudioFormats
    codec: AudioCodecs
    bit_rate: AudioBitRates
    sample_rate: AudioSampleRates
    channel: AudioChannels


@dataclass
class SpeechResult:
    """Result of audio Speech."""

    text: str | None
    result: SpeechResultState


@dataclass
class SpeechAudioProcessing:
    """Required and preferred input audio processing settings."""

    requires_external_vad: bool
    """True if an external voice activity detector (VAD) is required.

    If False, the speech-to-text entity must detect the end of speech itself.
    """

    prefers_auto_gain_enabled: bool
    """True if input audio should adjust gain automatically for best results."""

    prefers_noise_reduction_enabled: bool
    """True if input audio should apply noise reduction for best results."""


DEFAULT_AUDIO_PROCESSING = SpeechAudioProcessing(
    requires_external_vad=True,
    prefers_auto_gain_enabled=True,
    prefers_noise_reduction_enabled=True,
)
