"""Support for Speedtest.net internet speed testing sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_BYTES_RECEIVED,
    ATTR_BYTES_SENT,
    ATTR_SERVER_COUNTRY,
    ATTR_SERVER_ID,
    ATTR_SERVER_NAME,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Speedtestdotnet sensors."""

    speedtestcoordinator = hass.data[DOMAIN]

    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(SpeedtestSensor(speedtestcoordinator, sensor_type))

    async_add_entities(dev, True)


class SpeedtestSensor(Entity):
    """Implementation of a speedtest.net sensor."""

    def __init__(self, coordinator, sensor_type):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.coordinator = coordinator
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME} {self._name}"

    @property
    def unique_id(self):
        """Return sensor unique_id."""
        return self.name

    @property
    def state(self):
        """Return the state of the device."""
        if self.type == "ping":
            return self.coordinator.data["ping"]
        if self.type == "download":
            return round(self.coordinator.data["download"] / 10 ** 6, 2)
        if self.type == "upload":
            return round(self.coordinator.data["upload"] / 10 ** 6, 2)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        if self.type == "download":
            attributes.update(
                {ATTR_BYTES_RECEIVED: self.coordinator.data["bytes_received"]}
            )
        if self.type == "upload":
            attributes.update({ATTR_BYTES_SENT: self.coordinator.data["bytes_sent"]})
        attributes.update(
            {
                ATTR_SERVER_NAME: self.coordinator.data["server"]["name"],
                ATTR_SERVER_COUNTRY: self.coordinator.data["server"]["country"],
                ATTR_SERVER_ID: self.coordinator.data["server"]["id"],
            }
        )
        return attributes

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
