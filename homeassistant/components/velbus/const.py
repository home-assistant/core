"""Const for Velbus."""

from typing import Final

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
)

DOMAIN: Final = "velbus"

CONF_INTERFACE: Final = "interface"
CONF_MEMO_TEXT: Final = "memo_text"

SERVICE_SCAN: Final = "scan"
SERVICE_SYNC: Final = "sync_clock"
SERVICE_SET_MEMO_TEXT: Final = "set_memo_text"
SERVICE_CLEAR_CACHE: Final = "clear_cache"

PRESET_MODES: Final = {
    PRESET_ECO: "safe",
    PRESET_AWAY: "night",
    PRESET_HOME: "day",
    PRESET_COMFORT: "comfort",
}
