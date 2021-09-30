"""Constants for the crownstone integration."""
from __future__ import annotations

from typing import Final

# Platforms
DOMAIN: Final = "crownstone"
PLATFORMS: Final[list[str]] = ["light"]

# Listeners
SSE_LISTENERS: Final = "sse_listeners"
UART_LISTENERS: Final = "uart_listeners"

# Unique ID suffixes
CROWNSTONE_SUFFIX: Final = "crownstone"

# Signals (within integration)
SIG_CROWNSTONE_STATE_UPDATE: Final = "crownstone.crownstone_state_update"
SIG_CROWNSTONE_UPDATE: Final = "crownstone.crownstone_update"
SIG_UART_STATE_CHANGE: Final = "crownstone.uart_state_change"

# Config flow
CONF_USB_PATH: Final = "usb_path"
CONF_USB_MANUAL_PATH: Final = "usb_manual_path"
CONF_USB_SPHERE: Final = "usb_sphere"
# Options flow
CONF_USE_USB_OPTION: Final = "use_usb_option"
CONF_USB_SPHERE_OPTION: Final = "usb_sphere_option"
# USB config list entries
DONT_USE_USB: Final = "Don't use USB"
REFRESH_LIST: Final = "Refresh list"
MANUAL_PATH: Final = "Enter manually"

# Crownstone entity
CROWNSTONE_INCLUDE_TYPES: Final[dict[str, str]] = {
    "PLUG": "Plug",
    "BUILTIN": "Built-in",
    "BUILTIN_ONE": "Built-in One",
}

# Crownstone USB Dongle
CROWNSTONE_USB: Final = "CROWNSTONE_USB"
