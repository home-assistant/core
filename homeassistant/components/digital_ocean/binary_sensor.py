"""Support for monitoring the state of Digital Ocean droplets."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOVING,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_CREATED_AT,
    ATTR_DROPLET_ID,
    ATTR_DROPLET_NAME,
    ATTR_FEATURES,
    ATTR_IPV4_ADDRESS,
    ATTR_IPV6_ADDRESS,
    ATTR_MEMORY,
    ATTR_REGION,
    ATTR_VCPUS,
    ATTRIBUTION,
    CONF_DROPLETS,
    DATA_DIGITAL_OCEAN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Droplet"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DROPLETS): vol.All(cv.ensure_list, [cv.string])}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Digital Ocean droplet sensor."""
    digital = hass.data.get(DATA_DIGITAL_OCEAN)
    if not digital:
        return False

    droplets = config[CONF_DROPLETS]

    dev = []
    for droplet in droplets:
        droplet_id = digital.get_droplet_id(droplet)
        if droplet_id is None:
            _LOGGER.error("Droplet %s is not available", droplet)
            return False
        dev.append(DigitalOceanBinarySensor(digital, droplet_id))

    add_entities(dev, True)


class DigitalOceanBinarySensor(BinarySensorEntity):
    """Representation of a Digital Ocean droplet sensor."""

    def __init__(self, do, droplet_id):
        """Initialize a new Digital Ocean sensor."""
        self._digital_ocean = do
        self._droplet_id = droplet_id
        self._state = None
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.data.name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.data.status == "active"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOVING

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Digital Ocean droplet."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_CREATED_AT: self.data.created_at,
            ATTR_DROPLET_ID: self.data.id,
            ATTR_DROPLET_NAME: self.data.name,
            ATTR_FEATURES: self.data.features,
            ATTR_IPV4_ADDRESS: self.data.ip_address,
            ATTR_IPV6_ADDRESS: self.data.ip_v6_address,
            ATTR_MEMORY: self.data.memory,
            ATTR_REGION: self.data.region["name"],
            ATTR_VCPUS: self.data.vcpus,
        }

    def update(self):
        """Update state of sensor."""
        self._digital_ocean.update()

        for droplet in self._digital_ocean.data:
            if droplet.id == self._droplet_id:
                self.data = droplet
