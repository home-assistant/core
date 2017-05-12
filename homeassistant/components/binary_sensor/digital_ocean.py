"""
Support for monitoring the state of Digital Ocean droplets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.digital_ocean/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.digital_ocean import (
    CONF_DROPLETS, ATTR_CREATED_AT, ATTR_DROPLET_ID, ATTR_DROPLET_NAME,
    ATTR_FEATURES, ATTR_IPV4_ADDRESS, ATTR_IPV6_ADDRESS, ATTR_MEMORY,
    ATTR_REGION, ATTR_VCPUS)
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Droplet'
DEFAULT_SENSOR_CLASS = 'motion'
DEPENDENCIES = ['digital_ocean']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DROPLETS): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Digital Ocean droplet sensor."""
    digital_ocean = get_component('digital_ocean')
    droplets = config.get(CONF_DROPLETS)

    dev = []
    for droplet in droplets:
        droplet_id = digital_ocean.DIGITAL_OCEAN.get_droplet_id(droplet)
        if droplet_id is None:
            _LOGGER.error("Droplet %s is not available", droplet)
            return False
        dev.append(DigitalOceanBinarySensor(
            digital_ocean.DIGITAL_OCEAN, droplet_id))

    add_devices(dev)


class DigitalOceanBinarySensor(BinarySensorDevice):
    """Representation of a Digital Ocean droplet sensor."""

    def __init__(self, do, droplet_id):
        """Initialize a new Digital Ocean sensor."""
        self._digital_ocean = do
        self._droplet_id = droplet_id
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.data.name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.data.status == 'active'

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_SENSOR_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Digital Ocean droplet."""
        return {
            ATTR_CREATED_AT: self.data.created_at,
            ATTR_DROPLET_ID: self.data.id,
            ATTR_DROPLET_NAME: self.data.name,
            ATTR_FEATURES: self.data.features,
            ATTR_IPV4_ADDRESS: self.data.ip_address,
            ATTR_IPV6_ADDRESS: self.data.ip_v6_address,
            ATTR_MEMORY: self.data.memory,
            ATTR_REGION: self.data.region['name'],
            ATTR_VCPUS: self.data.vcpus,
        }

    def update(self):
        """Update state of sensor."""
        self._digital_ocean.update()

        for droplet in self._digital_ocean.data:
            if droplet.id == self._droplet_id:
                self.data = droplet
