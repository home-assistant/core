"""Constants for the Victron Modbus integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "victron_modbus"

# Every supported device answers Modbus/UDP on this port, as unit 1.
PORT: Final = 502
UNIT_ID: Final = 1

MANUFACTURER: Final = "Victron Energy"

# Power changes from moment to moment, and automations act on it; the other
# readings (voltage, current, energy counters, frequency) change slowly.
POWER_SCAN_INTERVAL: Final = timedelta(seconds=1)
READINGS_SCAN_INTERVAL: Final = timedelta(seconds=10)
