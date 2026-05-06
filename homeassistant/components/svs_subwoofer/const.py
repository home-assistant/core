"""Constants for SVS Subwoofer integration."""

from typing import Final

DOMAIN: Final = "svs_subwoofer"

# BLE Constants
SVS_SERVICE_UUID: Final = "1fee6acf-a826-4e37-9635-4d8a01642c5d"
SVS_CHAR_UUID: Final = "6409d79d-cd28-479c-a639-92f9e1948b43"

# Parameter limits - Volume
VOLUME_MIN: Final = -60
VOLUME_MAX: Final = 0
VOLUME_STEP: Final = 1

# Parameter limits - Phase
PHASE_MIN: Final = 0
PHASE_MAX: Final = 180
PHASE_STEP: Final = 1

# Parameter limits - Low Pass Filter
LPF_FREQ_MIN: Final = 30
LPF_FREQ_MAX: Final = 200
LPF_FREQ_STEP: Final = 1
LPF_SLOPES: Final = [6, 12, 18, 24]

# Parameter limits - Parametric EQ
PEQ_FREQ_MIN: Final = 20
PEQ_FREQ_MAX: Final = 200
PEQ_FREQ_STEP: Final = 1
PEQ_BOOST_MIN: Final = -12.0
PEQ_BOOST_MAX: Final = 6.0
PEQ_BOOST_STEP: Final = 0.1
PEQ_Q_MIN: Final = 0.2
PEQ_Q_MAX: Final = 10.0
PEQ_Q_STEP: Final = 0.1

# Parameter limits - Room Gain
ROOM_GAIN_FREQUENCIES: Final = [25, 31, 40]
ROOM_GAIN_SLOPES: Final = [6, 12]

# Standby modes
STANDBY_MODES: Final = ["Auto ON", "Trigger", "ON"]
STANDBY_MODE_MAP: Final = {"Auto ON": 0, "Trigger": 1, "ON": 2}

# Presets
PRESETS: Final = ["Preset 1", "Preset 2", "Preset 3", "Default"]
PRESET_MAP: Final = {"Preset 1": 1, "Preset 2": 2, "Preset 3": 3, "Default": 4}

# Command rate limiting (seconds)
COMMAND_DELAY: Final = 0.2

# Device automation - Event type
EVENT_SVS_SUBWOOFER: Final = "svs_subwoofer_event"

# Device automation - Trigger types
TRIGGER_TYPE_CONNECTED: Final = "connected"
TRIGGER_TYPE_DISCONNECTED: Final = "disconnected"
TRIGGER_TYPE_PRESET_LOADED: Final = "preset_loaded"
TRIGGER_TYPES: Final = {
    TRIGGER_TYPE_CONNECTED,
    TRIGGER_TYPE_DISCONNECTED,
    TRIGGER_TYPE_PRESET_LOADED,
}

# Device automation - Trigger subtypes (for presets)
TRIGGER_SUBTYPE_PRESET_1: Final = "preset_1"
TRIGGER_SUBTYPE_PRESET_2: Final = "preset_2"
TRIGGER_SUBTYPE_PRESET_3: Final = "preset_3"
TRIGGER_SUBTYPE_DEFAULT: Final = "default"
TRIGGER_SUBTYPES_PRESET: Final = (
    TRIGGER_SUBTYPE_PRESET_1,
    TRIGGER_SUBTYPE_PRESET_2,
    TRIGGER_SUBTYPE_PRESET_3,
    TRIGGER_SUBTYPE_DEFAULT,
)

# Device automation - Action types
ACTION_TYPE_LOAD_PRESET: Final = "load_preset"
ACTION_TYPE_SAVE_PRESET: Final = "save_preset"
ACTION_TYPE_SET_VOLUME: Final = "set_volume"
ACTION_TYPE_RECONNECT: Final = "reconnect"
ACTION_TYPES: Final = {
    ACTION_TYPE_LOAD_PRESET,
    ACTION_TYPE_SAVE_PRESET,
    ACTION_TYPE_SET_VOLUME,
    ACTION_TYPE_RECONNECT,
}

# Action parameters
CONF_PRESET: Final = "preset"
CONF_VOLUME: Final = "volume"

# Service names
SERVICE_SYNC_FROM: Final = "sync_from"
SERVICE_SET_VOLUME: Final = "set_volume"
SERVICE_LOAD_PRESET: Final = "load_preset"

# Parameters that can be synced between subwoofers
SYNCABLE_PARAMS: Final = [
    "VOLUME",
    "PHASE",
    "LOW_PASS_FILTER_ENABLE",
    "LOW_PASS_FILTER_FREQ",
    "LOW_PASS_FILTER_SLOPE",
    "PEQ1_ENABLE",
    "PEQ1_FREQ",
    "PEQ1_BOOST",
    "PEQ1_QFACTOR",
    "PEQ2_ENABLE",
    "PEQ2_FREQ",
    "PEQ2_BOOST",
    "PEQ2_QFACTOR",
    "PEQ3_ENABLE",
    "PEQ3_FREQ",
    "PEQ3_BOOST",
    "PEQ3_QFACTOR",
    "ROOM_GAIN_ENABLE",
    "ROOM_GAIN_FREQ",
    "ROOM_GAIN_SLOPE",
    "STANDBY",
    "POLARITY",
]
