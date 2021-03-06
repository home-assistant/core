"""Support for Eight Sleep binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)

from . import EightSleepHeatEntity
from .const import DATA_EIGHT, NAME_MAP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Discover and configure Eight Sleep binary sensors."""

    eight = hass.data[DATA_EIGHT]

    sensor_list = []

    if eight.users:
        for user in eight.users:
            obj = eight.users[user]
            sensor_list.append(EightPresenceBinarySensor(eight, obj.side))
    else:
        # No users, cannot continue
        return False

    async_add_entities(sensor_list, True)


class EightPresenceBinarySensor(EightSleepHeatEntity, BinarySensorEntity):
    """Representation of a Eight Sleep heat-based sensor."""

    def __init__(self, eight, side):
        """Initialize the sensor."""
        super().__init__(eight)

        self._mapped_name = NAME_MAP.get(f"{side}_presence")
        self._name = f"Eight Sleep - {self._mapped_name}"
        self._state = None

        self._side = side
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug(
            "Presence Sensor, Side: %s, User: %s",
            self._side,
            self._userid,
        )

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for the binary sensor."""
        return f"{self._userid}_presence"

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return DEVICE_CLASS_PRESENCE

    async def async_update(self):
        """Retrieve latest state."""
        self._state = self._usrobj.bed_presence
