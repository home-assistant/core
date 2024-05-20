"""Constants for Dreo Component."""
DOMAIN = "dreo"

# key
MANAGER = "manager"
PLATFORMS = "platforms"
DEVICE = "devices"

# platforms
PLATFORMS_CONFIG = {
    "DR-HTF001S": ["fan"],
    "DR-HTF002S": ["fan"],
    "DR-HTF004S": ["fan"],
    "DR-HTF005S": ["fan"],
    "DR-HTF005S-2": ["fan"],
    "DR-HTF007S": ["fan"],
    "DR-HTF008S": ["fan"],
    "DR-HTF009S": ["fan"],
    "DR-HTF010S": ["fan"]
}

# fan
FAN = "fan"
FAN_DEVICE = "fan_devices"
FAN_CONFIG = {
    "DR-HTF001S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 6)
    },
    "DR-HTF002S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 6)
    },
    "DR-HTF004S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 12)
    },
    "DR-HTF005S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 9)
    },
    "DR-HTF005S-2": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 12)
    },
    "DR-HTF007S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 4)
    },
    "DR-HTF008S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 5)
    },
    "DR-HTF009S": {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": (1, 9)
    },
    "DR-HTF010S": {
        "preset_modes": ["Sleep", "Auto", "Normal"],
        "speed_range": (1, 12)
    }
}

# light
LIGHT = "light"
LIGHT_DEVICE = "light_devices"
...