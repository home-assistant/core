"""
Support for monitoring the state of Digital Ocean droplets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.digital_ocean/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.vultr import (
    CONF_SUBS, ATTR_CREATED_AT, ATTR_SUBSCRIPTION_ID, ATTR_SUBSCRIPTION_NAME,
    ATTR_IPV4_ADDRESS, ATTR_IPV6_ADDRESS, ATTR_MEMORY, ATTR_DISK,
    ATTR_COST_PER_MONTH, ATTR_OS, ATTR_REGION, ATTR_VCPUS, DATA_VULTR)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Vultr_Server'
DEPENDENCIES = ['vultr']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SUBS): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vultr subscription (server) sensor."""
    vultr = hass.data.get(DATA_VULTR)
    if not vultr:
        return False

    subscriptions = config.get(CONF_SUBS)

    dev = []
    for subscription in subscriptions:
        dev.append(VultrBinarySensor(vultr, subscription))

    add_devices(dev, True)


class VultrBinarySensor(BinarySensorDevice):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr, subscription):
        """Initialize a new Vultr sensor."""
        self._vultr = vultr
        self._subscription = subscription
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.data.get('label', DEFAULT_NAME)

    @property
    def icon(self):
        """Return the icon of this server."""
        return 'mdi:server' if self.is_on else 'mdi:server-off'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.data.get('status') == 'active'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Vultr subscription."""
        if self.data:
            return {
                ATTR_COST_PER_MONTH: self.data['cost_per_month'],
                ATTR_CREATED_AT: self.data['date_created'],
                ATTR_DISK: self.data['disk'],
                ATTR_SUBSCRIPTION_ID: self.data['SUBID'],
                ATTR_SUBSCRIPTION_NAME: self.data['label'],
                ATTR_IPV4_ADDRESS: self.data['main_ip'],
                ATTR_IPV6_ADDRESS: self.data['v6_main_ip'],
                ATTR_MEMORY: self.data['ram'],
                ATTR_OS: self.data['os'],
                ATTR_REGION: self.data['location'],
                ATTR_VCPUS: self.data['vcpu_count'],
            }

        return {}

    def update(self):
        """Update state of sensor."""
        # TODO: This needed here?
#        self._vultr.update()

        _LOGGER.debug("Updating Vultr subscription: %s", self._subscription)
        self.data = self._vultr.data.get(self._subscription, {})
