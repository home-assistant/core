"""Support for Vultr."""
from datetime import timedelta
import logging

import voluptuous as vol
from vultr import Vultr as VultrAPI

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_AUTO_BACKUPS = "auto_backups"
ATTR_ALLOWED_BANDWIDTH = "allowed_bandwidth_gb"
ATTR_COST_PER_MONTH = "cost_per_month"
ATTR_CURRENT_BANDWIDTH_USED = "current_bandwidth_gb"
ATTR_CREATED_AT = "created_at"
ATTR_DISK = "disk"
ATTR_SUBSCRIPTION_ID = "subid"
ATTR_SUBSCRIPTION_NAME = "label"
ATTR_IPV4_ADDRESS = "ipv4_address"
ATTR_IPV6_ADDRESS = "ipv6_address"
ATTR_MEMORY = "memory"
ATTR_OS = "os"
ATTR_PENDING_CHARGES = "pending_charges"
ATTR_REGION = "region"
ATTR_VCPUS = "vcpus"

CONF_SUBSCRIPTION = "subscription"

DATA_VULTR = "data_vultr"
DOMAIN = "vultr"

NOTIFICATION_ID = "vultr_notification"
NOTIFICATION_TITLE = "Vultr Setup"

VULTR_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_API_KEY): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Vultr component."""
    api_key = config[DOMAIN].get(CONF_API_KEY)

    vultr = Vultr(api_key)

    try:
        vultr.update()
    except RuntimeError as ex:
        _LOGGER.error("Failed to make update API request because: %s", ex)
        persistent_notification.create(
            hass,
            "Error: {}" "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    hass.data[DATA_VULTR] = vultr
    return True


class Vultr:
    """Handle all communication with the Vultr API."""

    def __init__(self, api_key):
        """Initialize the Vultr connection."""

        self._api_key = api_key
        self.data = None
        self.api = VultrAPI(self._api_key)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Vultr API."""
        self.data = self.api.server_list()

    def _force_update(self):
        """Use the data from Vultr API."""
        self.data = self.api.server_list()

    def halt(self, subscription):
        """Halt a subscription (hard power off)."""
        self.api.server_halt(subscription)
        self._force_update()

    def start(self, subscription):
        """Start a subscription."""
        self.api.server_start(subscription)
        self._force_update()
