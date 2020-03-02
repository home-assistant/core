"""Constants for the KEF component."""
DOMAIN = "kef"

SERVICE_MODE = "set_mode"
SERVICE_DESK_DB = "set_desk_db"
SERVICE_WALL_DB = "set_wall_db"
SERVICE_TREBLE_DB = "set_treble_db"
SERVICE_HIGH_HZ = "set_high_hz"
SERVICE_LOW_HZ = "set_low_hz"
SERVICE_SUB_DB = "set_sub_db"
SERVICE_UPDATE_DSP = "update_dsp"

SLIDERS = [
    ("desk_db", "db"),
    ("wall_db", "db"),
    ("treble_db", "db"),
    ("high_hz", "hz"),
    ("low_hz", "hz"),
    ("sub_db", "db"),
]
