"""Constants for the Hegel integration."""

DOMAIN = "hegel"
DEFAULT_PORT = 50001

CONF_MODEL = "model"
CONF_MAX_VOLUME = "max_volume"  # 1.0 means amp's internal max

HEARTBEAT_TIMEOUT_MINUTES = 3

MODEL_INPUTS = {
    "Röst": [
        "Balanced",
        "Analog 1",
        "Analog 2",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
    "H95": [
        "Analog 1",
        "Analog 2",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
    "H120": [
        "Balanced",
        "Analog 1",
        "Analog 2",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
    "H190": [
        "Balanced",
        "Analog 1",
        "Analog 2",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
    "H190V": [
        "XLR",
        "Analog 1",
        "Analog 2",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
        "Phono",
    ],
    "H390": [
        "XLR",
        "Analog 1",
        "Analog 2",
        "BNC",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
    "H590": [
        "XLR 1",
        "XLR 2",
        "Analog 1",
        "Analog 2",
        "BNC",
        "Coaxial",
        "Optical 1",
        "Optical 2",
        "Optical 3",
        "USB",
        "Network",
    ],
}
