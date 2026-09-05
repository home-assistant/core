"""Constants for the LaCrosse integration."""

from enum import IntFlag

DOMAIN = "lacrosse"

CONF_BATTERY = "battery"
CONF_BAUD = "baud"
CONF_DATARATE = "datarate"
CONF_EXPIRE_AFTER = "expire_after"
CONF_FREQUENCY = "frequency"
CONF_HUMIDITY = "humidity"
CONF_JEELINK_LED = "led"
CONF_NEW_ID = "new_id"
CONF_TEMPERATURE = "temperature"
CONF_TOGGLE_INTERVAL = "toggle_interval"
CONF_TOGGLE_MASK = "toggle_mask"

DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD = 57600


class LaCrosseSensorType(IntFlag):
    """Value types a LaCrosse sensor can report."""

    BATTERY = 1
    HUMIDITY = 2
    TEMPERATURE = 4

    @property
    def key(self) -> str:
        """Return the configuration key of a single sensor type."""
        return str(self.name).lower()

    def sensor_key(self, sensor_id: int) -> str:
        """Return the storage key of a sensor with this type."""
        return f"{sensor_id}_{self.key}"


TYPES = [sensor_type.key for sensor_type in LaCrosseSensorType]
