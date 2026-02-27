"""Constants for the Sharp COCORO Air integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "sharp_cocoro_air"
PLATFORMS: list[Platform] = [Platform.FAN]

SCAN_INTERVAL = timedelta(seconds=60)

# Maps API mode key -> display name
OPERATION_MODES = {
    "auto": "Auto",
    "night": "Night",
    "pollen": "Pollen",
    "silent": "Silent",
    "medium": "Medium",
    "high": "High",
    "ai_auto": "AI Auto",
    "realize": "Realize",
}

# Reverse: display name -> API key (for decoding current mode from ECHONET data)
DISPLAY_TO_API_MODE = {v: k for k, v in OPERATION_MODES.items()}

CLEANING_MODES = {
    0x41: "Cleaning",
    0x42: "Humidifying",
    0x43: "Cleaning + Humidifying",
    0x44: "Off",
}
