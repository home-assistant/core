"""Constants for the LaCrosse integration."""

from enum import IntFlag

from homeassistant.util import slugify

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
    sensor_id: int,
    sensor_type: LaCrosseSensorType,
    friendly_name: str | None = None,
) -> str:
    """Return the entity key for a sensor type."""
    name = slugify(friendly_name.strip()) if friendly_name else ""
    return f"{name or sensor_id}_{sensor_type.key}"


TYPES = [sensor_type.key for sensor_type in LaCrosseSensorType]
