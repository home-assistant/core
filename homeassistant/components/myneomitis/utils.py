"""Utility functions for the MyNeomitis integration.

This module provides helper functions and constants for the MyNeomitis integration.
"""

PRESET_MODE_MAP = {
    "comfort": 1,
    "eco": 2,
    "antifrost": 3,
    "standby": 4,
    "boost": 6,
    "setpoint": 8,
    "comfort_plus": 20,
    "eco_1": 40,
    "eco_2": 41,
    "auto": 60,
}

PRESET_MODE_MAP_RELAIS = {
    "on": 1,
    "off": 2,
    "auto": 60,
}

PRESET_MODE_MAP_UFH = {
    "heating": 0,
    "cooling": 1,
}

REVERSE_PRESET_MODE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

REVERSE_PRESET_MODE_MAP_RELAIS = {v: k for k, v in PRESET_MODE_MAP_RELAIS.items()}

REVERSE_PRESET_MODE_MAP_UFH = {v: k for k, v in PRESET_MODE_MAP_UFH.items()}
