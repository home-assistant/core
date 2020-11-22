"""Support for the Hive binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    BinarySensorEntity,
)

from . import DATA_HIVE, DOMAIN, HiveEntity

DEVICETYPE_DEVICE_CLASS = {
    "motionsensor": DEVICE_CLASS_MOTION,
    "contactsensor": DEVICE_CLASS_OPENING,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive sensor devices."""
    if discovery_info is None:
        return

    session = hass.data.get(DATA_HIVE)
    devs = []
    for dev in discovery_info:
        devs.append(HiveBinarySensorEntity(session, dev))
    add_entities(devs)


class HiveBinarySensorEntity(HiveEntity, BinarySensorEntity):
    """Representation of a Hive binary sensor."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICETYPE_DEVICE_CLASS.get(self.node_device_type)

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self.node_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.session.sensor.get_state(self.node_id, self.node_device_type)

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(self.node_id)
