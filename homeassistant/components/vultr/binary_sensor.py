"""Support for monitoring the state of Vultr subscriptions (VPS)."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_ALLOWED_BANDWIDTH,
    ATTR_AUTO_BACKUPS,
    ATTR_COST_PER_MONTH,
    ATTR_CREATED_AT,
    ATTR_DISK,
    ATTR_IPV4_ADDRESS,
    ATTR_IPV6_ADDRESS,
    ATTR_MEMORY,
    ATTR_OS,
    ATTR_REGION,
    ATTR_SUBSCRIPTION_ID,
    ATTR_SUBSCRIPTION_NAME,
    ATTR_VCPUS,
    CONF_SUBSCRIPTION,
    DATA_VULTR,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_CLASS = "power"
DEFAULT_NAME = "Vultr {}"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SUBSCRIPTION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Vultr subscription (server) binary sensor."""
    vultr = hass.data[DATA_VULTR]

    subscription = config.get(CONF_SUBSCRIPTION)
    name = config.get(CONF_NAME)

    if subscription not in vultr.data:
        _LOGGER.error("Subscription %s not found", subscription)
        return

    add_entities([VultrBinarySensor(vultr, subscription, name)], True)


class VultrBinarySensor(BinarySensorEntity):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr, subscription, name):
        """Initialize a new Vultr binary sensor."""
        self._vultr = vultr
        self._name = name

        self.subscription = subscription
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return self._name.format(self.data["label"])
        except (KeyError, TypeError):
            return self._name

    @property
    def icon(self):
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.data["power_status"] == "running"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Vultr subscription."""
        return {
            ATTR_ALLOWED_BANDWIDTH: self.data.get("allowed_bandwidth_gb"),
            ATTR_AUTO_BACKUPS: self.data.get("auto_backups"),
            ATTR_COST_PER_MONTH: self.data.get("cost_per_month"),
            ATTR_CREATED_AT: self.data.get("date_created"),
            ATTR_DISK: self.data.get("disk"),
            ATTR_IPV4_ADDRESS: self.data.get("main_ip"),
            ATTR_IPV6_ADDRESS: self.data.get("v6_main_ip"),
            ATTR_MEMORY: self.data.get("ram"),
            ATTR_OS: self.data.get("os"),
            ATTR_REGION: self.data.get("location"),
            ATTR_SUBSCRIPTION_ID: self.data.get("SUBID"),
            ATTR_SUBSCRIPTION_NAME: self.data.get("label"),
            ATTR_VCPUS: self.data.get("vcpu_count"),
        }

    def update(self):
        """Update state of sensor."""
        self._vultr.update()
        self.data = self._vultr.data[self.subscription]
