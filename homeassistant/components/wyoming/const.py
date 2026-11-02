"""Constants for the Wyoming integration."""

from enum import StrEnum

DOMAIN = "wyoming"

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
SAMPLE_CHANNELS = 1


class WyomingTextToSpeechOption(StrEnum):
    """Store keys for the Wyoming text-to-speech options."""

    # For multi-speaker voices, this is the name of the selected speaker.
    SPEAKER = "speaker"


# Former name of the speaker option, kept for the integrations still using it
ATTR_SPEAKER = WyomingTextToSpeechOption.SPEAKER
