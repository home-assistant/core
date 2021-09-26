"""Constants for the KEF component."""
DOMAIN = "kef_custom"

CONF_MAX_VOLUME = "maximum_volume"
CONF_VOLUME_STEP = "volume_step"
CONF_INVERSE_SPEAKER_MODE = "inverse_speaker_mode"
CONF_SUPPORTS_ON = "supports_on"
CONF_STANDBY_TIME = "standby_time"

DEFAULT_NAME = "KEF"
DEFAULT_PORT = 50001
DEFAULT_MAX_VOLUME = 0.5
DEFAULT_VOLUME_STEP = 0.05
DEFAULT_INVERSE_SPEAKER_MODE = False
DEFAULT_SUPPORTS_ON = True

SLIDERS = [
    ("desk_db", "db"),
    ("wall_db", "db"),
    ("treble_db", "db"),
    ("high_hz", "hz"),
    ("low_hz", "hz"),
    ("sub_db", "db"),
]
