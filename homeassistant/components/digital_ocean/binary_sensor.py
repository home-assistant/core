"""Support for monitoring the state of Digital Ocean droplets."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Digital Ocean droplet sensor."""
    if not (digital := hass.data.get(DATA_DIGITAL_OCEAN)):
        return

    droplets = config[CONF_DROPLETS]

    dev = []
    for droplet in droplets:
        if (droplet_id := digital.get_droplet_id(droplet)) is None:
            _LOGGER.error("Droplet %s is not available", droplet)
            return
        dev.append(DigitalOceanBinarySensor(digital, droplet_id))

    add_entities(dev, True)


class DigitalOceanBinarySensor(BinarySensorEntity):
    """Representation of a Digital Ocean droplet sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, do, droplet_id):  # pylint: disable=invalid-name
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
        return BinarySensorDeviceClass.MOVING

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the Digital Ocean droplet."""
        return {
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

    def update(self) -> None:
        """Update state of sensor."""
        self._digital_ocean.update()

        for droplet in self._digital_ocean.data:
            if droplet.id == self._droplet_id:
                self.data = droplet
