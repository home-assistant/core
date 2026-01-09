"""Constants for the Hidromotic integration."""

DOMAIN = "hidromotic"

# Output types from web.js (tipo & 0xF0)
OUTPUT_TYPE_MANGUERA = 0x10  # Hose
OUTPUT_TYPE_TANQUE = 0x20  # Tank
OUTPUT_TYPE_ZONA = 0x40  # Zone (flooding zone)
OUTPUT_TYPE_PISCINA = 0x50  # Pool
OUTPUT_TYPE_CICLON = 0x60  # Cyclon

# Output states (estado)
STATE_OFF = 0
STATE_ON = 1
STATE_PAUSED = 4
STATE_WAITING = 5
STATE_DISABLED = 7  # Disconnected/disabled

# Tank levels (nivel)
TANK_FULL = 0
TANK_EMPTY = 1
