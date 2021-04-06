"""Constants for the siren component."""

DOMAIN = "siren"

ATTR_TONE = "tone"

ATTR_DEFAULT_TONE = "default_tone"
ATTR_AVAILABLE_TONES = "available_tones"
ATTR_DURATION = "duration"
ATTR_VOLUME_LEVEL = "volume_level"

SUPPORT_TURN_ON = 1
SUPPORT_TURN_OFF = 2
SUPPORT_TONES = 4
SUPPORT_VOLUME_SET = 8
SUPPORT_DURATION = 16

SERVICE_SET_DEFAULT_DURATION = "set_default_duration"
SERVICE_SET_DEFAULT_TONE = "set_default_tone"
SERVICE_SET_VOLUME_LEVEL = "set_volume_level"
