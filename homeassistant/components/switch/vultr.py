"""
Support for interacting with Vultr subscriptions.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.vultr/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.vultr import (
    CONF_SUBSCRIPTION, ATTR_AUTO_BACKUPS, ATTR_ALLOWED_BANDWIDTH,
    ATTR_CREATED_AT, ATTR_SUBSCRIPTION_ID, ATTR_SUBSCRIPTION_NAME,
    ATTR_IPV4_ADDRESS, ATTR_IPV6_ADDRESS, ATTR_MEMORY, ATTR_DISK,
    ATTR_COST_PER_MONTH, ATTR_OS, ATTR_REGION, ATTR_VCPUS, DATA_VULTR)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Vultr {}'
DEPENDENCIES = ['vultr']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SUBSCRIPTION): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vultr subscription switch."""
    vultr = hass.data[DATA_VULTR]

    subscription = config.get(CONF_SUBSCRIPTION)
    name = config.get(CONF_NAME)

    if subscription not in vultr.data:
        _LOGGER.error("Subscription %s not found", subscription)
        return False

    add_devices([VultrSwitch(vultr, subscription, name)], True)


class VultrSwitch(SwitchDevice):
    """Representation of a Vultr subscription switch."""

    def __init__(self, vultr, subscription, name):
        """Initialize a new Vultr switch."""
        self._vultr = vultr
        self._name = name

        self.subscription = subscription
        self.data = None

    @property
    def name(self):
        """Return the name of the switch."""
        try:
            return self._name.format(self.data['label'])
        except (TypeError, KeyError):
            return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.data['power_status'] == 'running'

    @property
    def icon(self):
        """Return the icon of this server."""
        return 'mdi:server' if self.is_on else 'mdi:server-off'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Vultr subscription."""
        return {
            ATTR_ALLOWED_BANDWIDTH: self.data.get('allowed_bandwidth_gb'),
            ATTR_AUTO_BACKUPS: self.data.get('auto_backups'),
            ATTR_COST_PER_MONTH: self.data.get('cost_per_month'),
            ATTR_CREATED_AT: self.data.get('date_created'),
            ATTR_DISK: self.data.get('disk'),
            ATTR_IPV4_ADDRESS: self.data.get('main_ip'),
            ATTR_IPV6_ADDRESS: self.data.get('v6_main_ip'),
            ATTR_MEMORY: self.data.get('ram'),
            ATTR_OS: self.data.get('os'),
            ATTR_REGION: self.data.get('location'),
            ATTR_SUBSCRIPTION_ID: self.data.get('SUBID'),
            ATTR_SUBSCRIPTION_NAME: self.data.get('label'),
            ATTR_VCPUS: self.data.get('vcpu_count'),
        }

    def turn_on(self):
        """Boot-up the subscription."""
        if self.data['power_status'] != 'running':
            self._vultr.start(self.subscription)

    def turn_off(self):
        """Halt the subscription."""
        if self.data['power_status'] == 'running':
            self._vultr.halt(self.subscription)

    def update(self):
        """Get the latest data from the device and update the data."""
        self._vultr.update()
        self.data = self._vultr.data[self.subscription]
