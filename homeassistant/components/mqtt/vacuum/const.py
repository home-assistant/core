"""Shared constants."""
from homeassistant.components import vacuum

MQTT_VACUUM_ATTRIBUTES_BLOCKED = frozenset(
    {
        vacuum.ATTR_BATTERY_ICON,
        vacuum.ATTR_BATTERY_LEVEL,
        vacuum.ATTR_FAN_SPEED,
    }
)
