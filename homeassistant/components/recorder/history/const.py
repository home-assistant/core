"""Constants for history."""

from typing import Final

STATE_KEY: Final = "state"
LAST_CHANGED_KEY: Final = "last_changed"

SIGNIFICANT_DOMAINS = {
    "climate",
    "device_tracker",
    "humidifier",
    "thermostat",
    "water_heater",
}
SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in SIGNIFICANT_DOMAINS]
IGNORE_DOMAINS = {"zone", "scene"}
NEED_ATTRIBUTE_DOMAINS = {
    "climate",
    "humidifier",
    "input_datetime",
    "thermostat",
    "water_heater",
}
