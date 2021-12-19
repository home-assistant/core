"""Constants for the wiffi component."""

from homeassistant.helpers.entity import EntityCategory

# Component domain, used to store component data in hass data.
DOMAIN = "wiffi"

# Default port for TCP server
DEFAULT_PORT = 8189

# Default timeout in minutes
DEFAULT_TIMEOUT = 3

# Signal name to send create/update to platform (sensor/binary_sensor)
CREATE_ENTITY_SIGNAL = "wiffi_create_entity_signal"
UPDATE_ENTITY_SIGNAL = "wiffi_update_entity_signal"
CHECK_ENTITIES_SIGNAL = "wiffi_check_entities_signal"

# map to determine HA entity category from wiffi's entity name
NAME_TO_ENTITY_CAT = {
    "rssi": EntityCategory.DIAGNOSTIC,
    "uptime": EntityCategory.DIAGNOSTIC,
    "ssid": EntityCategory.DIAGNOSTIC,
}
