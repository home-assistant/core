"""Const for Velbus."""

from typing import Final

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
)

DOMAIN: Final = "velbus"

CONF_TLS: Final = "tls"
CONF_VLP_FILE: Final = "vlp_file"

MANAGER_DEFAULT_PORT: Final = 4201

PRESET_MODES: Final = {
    PRESET_ECO: "safe",
    PRESET_AWAY: "night",
    PRESET_HOME: "day",
    PRESET_COMFORT: "comfort",
}
