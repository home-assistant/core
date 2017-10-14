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
    CONF_SUBS, ATTR_AUTO_BACKUPS, ATTR_ALLOWED_BANDWIDTH_GB, ATTR_CREATED_AT,
    ATTR_SUBSCRIPTION_ID, ATTR_SUBSCRIPTION_NAME,
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
        self.data = self._vultr.data.get(self._subscription)

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
        return self.data.get('power_status') == 'running'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Vultr subscription."""
        return {
            ATTR_ALLOWED_BANDWIDTH_GB: self.data.get('allowed_bandwidth_gb'),
            ATTR_AUTO_BACKUPS: self.data.get('auto_backups'),
            ATTR_COST_PER_MONTH: self.data.get('cost_per_month'),
            ATTR_CREATED_AT: self.data.get('date_created'),
            ATTR_DISK: self.data.get('disk'),
            ATTR_SUBSCRIPTION_ID: self.data.get('SUBID'),
            ATTR_SUBSCRIPTION_NAME: self.data.get('label'),
            ATTR_IPV4_ADDRESS: self.data.get('main_ip'),
            ATTR_IPV6_ADDRESS: self.data.get('v6_main_ip'),
            ATTR_MEMORY: self.data.get('ram'),
            ATTR_OS: self.data.get('os'),
            ATTR_REGION: self.data.get('location'),
            ATTR_VCPUS: self.data.get('vcpu_count'),
        }

    def update(self):
        """Update state of sensor."""
        self._vultr.update()
        self.data = self._vultr.data.get(self._subscription, {})
