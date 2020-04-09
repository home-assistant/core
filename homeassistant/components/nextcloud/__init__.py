"""The Nextcloud integration."""
from datetime import timedelta
import logging

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nextcloud"
NEXTCLOUD_COMPONENTS = ("sensor", "binary_sensor")
SCAN_INTERVAL = timedelta(seconds=60)

# Validate user configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
BINARY_SENSORS = (
    "nextcloud_system_enable_avatars",
    "nextcloud_system_enable_previews",
    "nextcloud_system_filelocking.enabled",
    "nextcloud_system_debug",
)

SENSORS = (
    "nextcloud_system_version",
    "nextcloud_system_theme",
    "nextcloud_system_memcache.local",
    "nextcloud_system_memcache.distributed",
    "nextcloud_system_memcache.locking",
    "nextcloud_system_freespace",
    "nextcloud_system_cpuload",
    "nextcloud_system_mem_total",
    "nextcloud_system_mem_free",
    "nextcloud_system_swap_total",
    "nextcloud_system_swap_free",
    "nextcloud_system_apps_num_installed",
    "nextcloud_system_apps_num_updates_available",
    "nextcloud_system_apps_app_updates_calendar",
    "nextcloud_system_apps_app_updates_contacts",
    "nextcloud_system_apps_app_updates_tasks",
    "nextcloud_system_apps_app_updates_twofactor_totp",
    "nextcloud_storage_num_users",
    "nextcloud_storage_num_files",
    "nextcloud_storage_num_storages",
    "nextcloud_storage_num_storages_local",
    "nextcloud_storage_num_storages_home",
    "nextcloud_storage_num_storages_other",
    "nextcloud_shares_num_shares",
    "nextcloud_shares_num_shares_user",
    "nextcloud_shares_num_shares_groups",
    "nextcloud_shares_num_shares_link",
    "nextcloud_shares_num_shares_mail",
    "nextcloud_shares_num_shares_room",
    "nextcloud_shares_num_shares_link_no_password",
    "nextcloud_shares_num_fed_shares_sent",
    "nextcloud_shares_num_fed_shares_received",
    "nextcloud_shares_permissions_3_1",
    "nextcloud_server_webserver",
    "nextcloud_server_php_version",
    "nextcloud_server_php_memory_limit",
    "nextcloud_server_php_max_execution_time",
    "nextcloud_server_php_upload_max_filesize",
    "nextcloud_database_type",
    "nextcloud_database_version",
    "nextcloud_database_version",
    "nextcloud_activeUsers_last5minutes",
    "nextcloud_activeUsers_last1hour",
    "nextcloud_activeUsers_last24hours",
)


def setup(hass, config):
    """Set up the Nextcloud integration."""
    # Fetch Nextcloud Monitor api data
    conf = config[DOMAIN]

    try:
        ncm = NextcloudMonitor(conf[CONF_URL], conf[CONF_USERNAME], conf[CONF_PASSWORD])
    except NextcloudMonitorError:
        _LOGGER.error("Nextcloud setup failed - Check configuration")

    hass.data[DOMAIN] = get_data_points(ncm.data)
    hass.data[DOMAIN]["instance"] = conf[CONF_URL]

    def nextcloud_update(event_time):
        """Update data from nextcloud api."""
        try:
            ncm.update()
        except NextcloudMonitorError:
            _LOGGER.error("Nextcloud update failed")
            return False

        hass.data[DOMAIN] = get_data_points(ncm.data)

    # Update sensors on time interval
    track_time_interval(hass, nextcloud_update, conf[CONF_SCAN_INTERVAL])

    for component in NEXTCLOUD_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


# Use recursion to create list of sensors & values based on nextcloud api data
def get_data_points(api_data, key_path="", leaf=False):
    """Use Recursion to discover data-points and values.

    Get dictionary of data-points by recursing through dict returned by api until
    the dictionary value does not contain another dictionary and use the
    resulting path of dictionary keys and resulting value as the name/value
    for the data-point.

    returns: dictionary of data-point/values
    """
    result = {}
    for key, value in api_data.items():
        if isinstance(value, dict):
            if leaf:
                key_path = f"{key}_"
            if not leaf:
                key_path += f"{key}_"
            leaf = True
            result.update(get_data_points(value, key_path, leaf))
        else:
            result[f"{DOMAIN}_{key_path}{key}"] = value
            leaf = False
    return result
