"""Support for MyChevy binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDevice,
)
from homeassistant.core import callback
from homeassistant.util import slugify

from . import DOMAIN as MYCHEVY_DOMAIN, UPDATE_TOPIC, EVBinarySensorConfig

_LOGGER = logging.getLogger(__name__)

SENSORS = [EVBinarySensorConfig("Plugged In", "plugged_in", "plug")]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MyChevy sensors."""
    if discovery_info is None:
        return

    sensors = []
    hub = hass.data[MYCHEVY_DOMAIN]
    for sconfig in SENSORS:
        for car in hub.cars:
            sensors.append(EVBinarySensor(hub, sconfig, car.vid))

    async_add_entities(sensors)


class EVBinarySensor(BinarySensorDevice):
    """Base EVSensor class.

    The only real difference between sensors is which units and what
    attribute from the car object they are returning. All logic can be
    built with just setting subclass attributes.
    """

    def __init__(self, connection, config, car_vid):
        """Initialize sensor with car connection."""
        self._conn = connection
        self._name = config.name
        self._attr = config.attr
        self._type = config.device_class
        self._is_on = None
        self._car_vid = car_vid
        self.entity_id = f"{BINARY_SENSOR_DOMAIN}.{MYCHEVY_DOMAIN}_{slugify(self._car.name)}_{slugify(self._name)}"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def is_on(self):
        """Return if on."""
        return self._is_on

    @property
    def _car(self):
        """Return the car."""
        return self._conn.get_car(self._car_vid)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            UPDATE_TOPIC, self.async_update_callback
        )

    @callback
    def async_update_callback(self):
        """Update state."""
        if self._car is not None:
            self._is_on = getattr(self._car, self._attr, None)
            self.async_write_ha_state()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
