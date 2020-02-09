"""Summary data from Nextcoud."""
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
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

# Assign domain
DOMAIN = "nextcloud"
# Set Default scan interval in seconds
SCAN_INTERVAL = timedelta(seconds=60)

# Validate user configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    }
)

# Add expected items and paths from nextcloud monitor api
NEXTCLOUD_ITEMS_EXPECTED = {
    "system_version": ["nextcloud", "system", "version"],
    "system_theme": ["nextcloud", "system", "theme"],
    "system_enable_avatars": ["nextcloud", "system", "enable_avatars"],
    "system_enable_previews": ["nextcloud", "system", "enable_previews"],
    "system_memcache.local": ["nextcloud", "system", "memcache.local"],
    "system_memcache.distributed": ["nextcloud", "system", "memcache.distributed"],
    "system_local": ["nextcloud", "system", "memcache.local"],
    "system_filelocking.enabled": ["nextcloud", "system", "filelocking.enabled"],
    "system_memcache.locking": ["nextcloud", "system", "memcache.locking"],
    "system_debug": ["nextcloud", "system", "debug"],
    "system_freespace": ["nextcloud", "system", "freespace"],
    "system_cpuload": ["nextcloud", "system", "cpuload"],
    "system_mem_total": ["nextcloud", "system", "mem_total"],
    "system_mem_free": ["nextcloud", "system", "mem_free"],
    "system_swap_total": ["nextcloud", "system", "swap_total"],
    "system_swap_free": ["nextcloud", "system", "swap_free"],
    "system_apps_num_installed": ["nextcloud", "system", "apps", "num_installed"],
    "system_apps_num_updates_available": [
        "nextcloud",
        "system",
        "apps",
        "num_updates_available",
    ],
    "system_apps_app_updates": ["nextcloud", "system", "apps", "app_updates"],
    "storage_num_users": ["nextcloud", "storage", "num_users"],
    "storage_num_files": ["nextcloud", "storage", "num_files"],
    "storage_num_storages": ["nextcloud", "storage", "num_storages"],
    "storage_num_storages_local": ["nextcloud", "storage", "num_storages_local"],
    "storage_num_storages_home": ["nextcloud", "storage", "num_storages_home"],
    "storage_num_storages_other": ["nextcloud", "storage", "num_storages_other"],
    "storage_num_shares": ["nextcloud", "shares", "num_shares"],
    "storage_num_shares_user": ["nextcloud", "shares", "num_shares_user"],
    "storage_num_shares_groups": ["nextcloud", "shares", "num_shares_groups"],
    "storage_num_shares_link": ["nextcloud", "shares", "num_shares_link"],
    "storage_num_shares_mail": ["nextcloud", "shares", "num_shares_mail"],
    "storage_num_shares_room": ["nextcloud", "shares", "num_shares_room"],
    "storage_num_shares_link_no_password": [
        "nextcloud",
        "shares",
        "num_shares_link_no_password",
    ],
    "storage_num_fed_shares_sent": ["nextcloud", "shares", "num_fed_shares_sent"],
    "storage_num_fed_shares_received": [
        "nextcloud",
        "shares",
        "num_fed_shares_received",
    ],
    "server_webserver": ["server", "webserver"],
    "server_php_version": ["server", "php", "version"],
    "server_php_memory_limit": ["server", "php", "memory_limit"],
    "server_php_max_execution_time": ["server", "php", "max_execution_time"],
    "server_php_max_file_size": ["server", "php", "upload_max_filesize"],
    "server_database_type": ["server", "database", "type"],
    "server_database_version": ["server", "database", "version"],
    "server_database_size": ["server", "database", "size"],
    "active_users_last_5_minutes": ["activeUsers", "last5minutes"],
    "active_users_last_1_hour": ["activeUsers", "last1hour"],
    "active_users_last_24_hours": ["activeUsers", "last24hours"],
}


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Nextcloud sensor."""
    # Fetch Nextcloud Monitor api data
    ncm = NextcloudMonitor(
        config[CONF_URL], config[CONF_USERNAME], config[CONF_PASSWORD]
    )

    hass.data[DOMAIN] = ncm.data

    def nextcloud_update(event_time):
        """Update data from nextcloud api."""
        ncm.update()
        hass.data[DOMAIN] = ncm.data

    # Update sensors on time interval
    track_time_interval(hass, nextcloud_update, config[CONF_SCAN_INTERVAL])

    # Create list of sensors based on available nextcloud api data
    sensors = []
    for name, dict_path in NEXTCLOUD_ITEMS_EXPECTED.items():
        sensors.append(NextcloudSensor(name, dict_path))

    # Setup sensors
    add_entities(sensors, True)


class NextcloudSensor(Entity):
    """Represents a Nextcloud sensor."""

    def __init__(self, item, value_path):
        """Initialize the Nextcloud sensor."""
        self.item = item
        self.value = None
        self.value_path = value_path

    @property
    def icon(self):
        """Return the icon for this sensor."""
        if self.item[:6] == "system":
            return "mdi:memory"
        if self.item[:7] == "storage":
            return "mdi:folder-account"
        if self.item[:6] == "server":
            return "mdi:server"
        if self.item[:6] == "active":
            return "mdi:account-multiple"
        return "mdi:cloud"

    @property
    def name(self):
        """Return the name for this sensor."""
        return f"{DOMAIN}_{self.item}"

    @property
    def state(self):
        """Return the state for this sensor."""
        return self.value

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return f"{DOMAIN}_{self.name}"

    def update(self):
        """Update the sensor."""
        data = self.hass.data[DOMAIN]
        for path in self.value_path:
            try:
                data = data[path]
            except KeyError:
                _LOGGER.warning("%s sensor information was not updated", self.name)
        self.value = data
