"""Monitor administrative summary data from Nextcoud"""
from datetime import timedelta
import logging

from nextcloudmonitor import NextcloudMonitor
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Assign domain
DOMAIN = "nextcloud"
# Set default scan interval in seconds
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER.error(SCAN_INTERVAL)
# Validate user configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the sensor platform."""
    # Set configuration variables
    url = config[CONF_URL]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    # Fetch Nextcloud Monitor api data
    ncm = NextcloudMonitor(url, username, password)
    # Add entities for each item returned
    sensor_items = [
        ("system_version", ncm.data["nextcloud"]["system"]["version"]),
        ("active_users_last_24_hours", ncm.data["activeUsers"]["last24hours"]),
    ]

    add_entities((NextcloudSensor(item, value) for item, value in sensor_items), True)


class NextcloudSensor(Entity):
    """Represents a Nextcloud sensor."""

    def __init__(self, item, value):
        """Initialize the Nextcloud sensor."""
        _LOGGER.info(item, value)
        self.item = item
        self.value = value

    @property
    def should_poll(self) -> bool:
        """Poll this sensor for updates."""
        return True

    @property
    def name(self) -> str:
        """Return the name for this sensor."""
        return f"{DOMAIN}_{self.item}"

    @property
    def state(self) -> str:
        """Return the state for this sensor."""
        return self.value

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join([DOMAIN, self.name])
