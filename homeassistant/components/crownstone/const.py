"""Constants for the crownstone integration."""
from typing import Final

# Platforms
DOMAIN: Final = "crownstone"
PLATFORMS: Final = ["light"]

# Listeners
SSE: Final = "sse_listeners"
UART: Final = "uart_listeners"

# Unique ID suffixes
CROWNSTONE_SUFFIX: Final = "crownstone"

# Signals (within integration)
SIG_CROWNSTONE_STATE_UPDATE: Final = "crownstone.crownstone_state_update"
SIG_CROWNSTONE_UPDATE: Final = "crownstone.crownstone_update"
SIG_UART_STATE_CHANGE: Final = "crownstone.uart_state_change"

# Abilities state
ABILITY_STATE: Final = {True: "Enabled", False: "Disabled"}

# Config flow
CONF_USB: Final = "usb"
CONF_USB_PATH: Final = "usb_path"
CONF_USE_CROWNSTONE_USB: Final = "use_crownstone_usb"

# Crownstone entity
CROWNSTONE_INCLUDE_TYPES: Final = {
    "PLUG": "Plug",
    "BUILTIN": "Built-in",
    "BUILTIN_ONE": "Built-in One",
}

# Crownstone USB Dongle
CROWNSTONE_USB: Final = "CROWNSTONE_USB"
