"""Constants for the Subaru integration."""

DOMAIN = "subaru"
DEFAULT_SCAN_INTERVAL = 300
MIN_SCAN_INTERVAL = 60
DEFAULT_HARD_POLL_INTERVAL = 7200
MIN_HARD_POLL_INTERVAL = 300
CONF_HARD_POLL_INTERVAL = "hard_poll_interval"

SUPPORTED_PLATFORMS = [
    "lock",
    "sensor",
]

ICONS = {
    "12V Battery Voltage": "mdi:car-battery",
    "Avg Fuel Consumption": "mdi:leaf",
    "Door Lock": "mdi:car-door-lock",
    "EV Battery Level": "mdi:battery-high",
    "EV Time to Full Charge": "mdi:car-electric",
    "EV Range": "mdi:ev-station",
    "External Temp": "mdi:thermometer",
    "Odometer": "mdi:counter",
    "Range": "mdi:gas-station",
    "Tire Pressure FL": "mdi:gauge",
    "Tire Pressure FR": "mdi:gauge",
    "Tire Pressure RL": "mdi:gauge",
    "Tire Pressure RR": "mdi:gauge",
}
