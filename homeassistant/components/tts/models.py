"""Text-to-speech data models."""
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Voice:
    """A TTS voice."""

    voice_id: str
    name: str


class SampleFormat(StrEnum):
    """Sample formats supported by ffmpeg."""

    U8 = "u8"
    S16 = "s16"
    S32 = "s32"
    FLT = "flt"
    DLB = "dbl"
    U8P = "u8p"
    S16P = "s16p"
    FLTP = "fltp"
    DBLP = "dblp"
    S64 = "s64"
    S64P = "s64p"


@dataclass(frozen=True)
class PreferredAudioFormat:
    """Details needed by ATTR_PREFERRED_FORMAT."""

    extension: str
    """File extension of format without a dot."""

    sample_rate: int | None = None
    """Sample rate in Hertz."""

    sample_format: SampleFormat | None = None
    """Format of samples."""

    num_channels: int | None = None
    """Number of channels per sample."""

    def needs_conversion(self, extension: str) -> bool:
        """Return True if an audio conversion would be needed."""
        if extension != self.extension:
            # Different audio format
            return True

        if (
            (self.sample_rate is not None)
            or (self.sample_format is not None)
            or (self.num_channels is not None)
        ):
            # May have different sample rate/format/channels
            return True

        return False
