"""Support for Plugwise power sensors."""
import logging

from . import PlugwiseNodeEntity
from .const import AVAILABLE_SENSOR_ID, DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plugwise sensor based on config_entry."""
    stick = hass.data[DOMAIN][entry.entry_id]["stick"]
    nodes_data = hass.data[DOMAIN][entry.entry_id]["sensor"]
    entities = []
    for mac in nodes_data:
        node = stick.node(mac)
        for sensor_type in node.get_sensors():
            if sensor_type in SENSORS:
                if sensor_type != AVAILABLE_SENSOR_ID:
                    entities.append(PlugwiseSensor(node, mac, sensor_type))
    async_add_entities(entities)


class PlugwiseSensor(PlugwiseNodeEntity):
    """Representation of a Plugwise sensor."""

    def __init__(self, node, mac, sensor_id):
        """Initialize a Node entity."""
        super().__init__(node, mac)
        self.sensor_id = sensor_id
        self.sensor_type = SENSORS[sensor_id]
        self.node_callbacks = (AVAILABLE_SENSOR_ID, sensor_id)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.sensor_type["class"]

    @property
    def entity_registry_enabled_default(self):
        """Return the sensor registration state."""
        return self.sensor_type["enabled_default"]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.sensor_type["icon"]

    @property
    def name(self):
        """Return the display name of this sensor."""
        return f"{self.sensor_type['name']} ({self._mac[-5:]})"

    @property
    def state(self):
        """Return the state of the sensor."""
        if getattr(self._node, self.sensor_type["state"])():
            return float(round(getattr(self._node, self.sensor_type["state"])(), 3))
        return None

    @property
    def unique_id(self):
        """Get unique ID."""
        return f"{self._mac}-{self.sensor_id}"

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self.sensor_type["unit"]
