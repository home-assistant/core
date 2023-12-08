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

    def __post_init__(self) -> None:
        """Finish initializing the metadata."""
        self.bit_rate = AudioBitRates(int(self.bit_rate))
        self.sample_rate = AudioSampleRates(int(self.sample_rate))
        self.channel = AudioChannels(int(self.channel))


@dataclass
class SpeechResult:
    """Result of audio Speech."""

    text: str | None
    result: SpeechResultState
