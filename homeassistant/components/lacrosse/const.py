"""Constants for the LaCrosse integration."""

from enum import IntFlag

DOMAIN = "lacrosse"

CONF_BATTERY = "battery"
CONF_BAUD = "baud"
CONF_DATARATE = "datarate"
CONF_DISABLED_BY_DEFAULT = "disabled_by_default"
CONF_EXPIRE_AFTER = "expire_after"
CONF_FREQUENCY = "frequency"
CONF_HUMIDITY = "humidity"
CONF_JEELINK_LED = "led"
CONF_NEW_ID = "new_id"
CONF_TEMPERATURE = "temperature"
CONF_TOGGLE_INTERVAL = "toggle_interval"
CONF_TOGGLE_MASK = "toggle_mask"
CONF_YAML_IMPORTED = "_yaml_imported"

DEFAULT_BAUD = 57600
DEFAULT_EXPIRE_AFTER = 300


class LaCrosseSensorType(IntFlag):
    """Value types a LaCrosse sensor can report."""

    BATTERY = 1
    HUMIDITY = 2
    TEMPERATURE = 4

    @property
    def key(self) -> str:
        """Return the configuration key of a single sensor type."""
        return str(self.name).lower()


def sensor_entity_key(
    subentry_id: str,
    sensor_type: str,
) -> str:
    """Return the entity key for a sensor type."""
    return f"{subentry_id}_{sensor_type}"


TYPES = [sensor_type.key for sensor_type in LaCrosseSensorType]
