"""Constants for the crownstone integration."""

# Platforms
DOMAIN = "crownstone"
LIGHT_PLATFORM = "light"

# Listeners
SSE = "sse_listeners"
UART = "uart_listeners"

# Unique ID suffixes
CROWNSTONE_SUFFIX = "crownstone"

# Signals (within integration)
SIG_CROWNSTONE_STATE_UPDATE = "crownstone.crownstone_state_update"
SIG_CROWNSTONE_UPDATE = "crownstone.crownstone_update"
SIG_UART_STATE_CHANGE = "crownstone.uart_state_change"

# Abilities state
ABILITY_STATE = {True: "Enabled", False: "Disabled"}

# Config flow
CONF_USB = "usb"
CONF_USB_PATH = "usb_path"
CONF_USE_CROWNSTONE_USB = "use_crownstone_usb"

# Crownstone entity
CROWNSTONE_INCLUDE_TYPES = {
    "PLUG": "Plug",
    "BUILTIN": "Built-in",
    "BUILTIN_ONE": "Built-in One",
}

# Crownstone USB Dongle
CROWNSTONE_USB = "CROWNSTONE_USB"
